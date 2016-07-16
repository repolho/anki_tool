#! /usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import os
import os.path
import sqlite3
import re
import json
import time
import datetime
import collections
import argparse

def rename_tag_in_notes(conn, tag, dst):
    """Renames a single tag in all notes"""
    n = 0
    found = []
    for row in conn.execute("select * from notes where tags like ?",
                            ('%'+tag+'%',)):
        tags = row['tags'].split()
        # Searching again because sql will return tags containing the tag we're
        # looking for, e.g. if src is 'a', sql will return 'a', 'ab', etc. We
        # will only rename the exact match
        if tag in tags:
            found.append(dict(row))

    for row in found:
        tags = row['tags'].split()
        tags.remove(tag)
        if dst:
            tags.append(dst)
        # remove duplicates and sort
        tags = sorted(set(tags))
        if not tags:
            tagstr = ''
        else:
            tagstr = ' {} '.format(' '.join(tags))
        conn.execute('update notes set tags=?,mod=?,usn=? where id=?',
                       (tagstr, int(time.time()), -1, row['id']))
        n += 1

    if not quiet:
        if n > 0:
            if dst:
                verb = 'renamed'
            else:
                verb = 'removed'
                print('Tag ‘'+tag+'’ successfully', verb, 'in',
                       n, 'notes.', file=sys.stderr)
        else:
            print('Tag ‘'+tag+'’ not found in any notes.', file=sys.stderr)

def rename_tags(conn, tags, remove=False):
    """Renames or removes all tags matching regular expressions"""

    if not remove and len(tags) < 2:
        print('Usage: mv_tags regex [regex]... destination',
              file=sys.stderr)
        return False
    elif remove and not tags:
        tags = []
        if not quiet:
            print('Reading from stdin...', file=sys.stderr)
        for tag in sys.stdin:
            tags.append(tag.rstrip())

    if not remove:
        dst = tags[-1]
        srcs = tags[:-1]
    else:
        dst = None
        srcs = tags

    row = conn.execute("select * from col where id=1").fetchone()
    if not row:
        print("Couldn't read collection.")
        return False

    try:
        tagsdict = json.loads(row['tags'])
        if type(tagsdict) != dict:
            raise ValueError
    except ValueError:
        print("Couldn't decode tags string:", row['tags'], file=sys.stderr)
        return False

    n = 0
    for target in srcs:
        found = False
        keys = list(tagsdict.keys())
        for tag in keys:
            if re.search(target, tag, re.I):
                found = True
                n += 1
                del tagsdict[tag]
                dsttag = re.sub(target, dst, tag)
                if dst:
                    tagsdict[dsttag] = -1

                try:
                    print("replace tag ", tag, " with ", dsttag)
                    rename_tag_in_notes(conn, tag, dsttag)
                except sqlite3.OperationalError:
                    return False
        if not found:
            if not quiet:
                print("Couldn't find tags matching ‘{}’, searching notes",
                      "for exact string.".format(target), file=sys.stderr)
            try:
                dsttag = re.sub(target, dst, tag)
                print("replace tag ", tag, " with ", dsttag, " (notfound?)")
                rename_tag_in_notes(conn, target, dsttag)
            except sqlite3.OperationalError:
                return False

    tagstr = json.dumps(tagsdict)
    conn.execute('update col set tags=?,mod=? where id=?',
                   (tagstr, int(time.time()*1000), row['id']))

    if not remove:
        verb = 'renamed'
    else:
        verb = 'removed'
    if n == 0:
        if not quiet:
            print('No tags were', verb, file=sys.stderr)
        return False
    elif not quiet:
        print(n, 'tag(s) successfully', verb, file=sys.stderr)

    return True

def remove_tags(conn, tags):
    return rename_tags(conn, tags, remove=True)

def get_card_ids(conn, note_id, return_deck_id=False):
    card_ids = []
    deck_id = None
    for row in conn.execute("select id,did from cards where nid = ?", (note_id,)):
        card_ids.append(row['id'])
        deck_id = row['did']
    if return_deck_id:
        return card_ids, deck_id
    return card_ids

def get_note_id(conn, card_id):
    # id is unique
    row = conn.execute("select nid from cards where id = ?", (card_id,)).fetchone()
    if row:
        return row['nid']
    return None

def search_notes(conn, regexps, only_field=None, only_tags=False, cards=False):
    if not regexps:
        regexps = []
        if not quiet:
            print('Reading from stdin...', file=sys.stderr)
        for regex in sys.stdin:
            regexps.append(regex.rstrip())

    success = False
    for row in conn.execute('select id,mid,flds,tags,sfld from notes'):
        tags = row['tags'].split()
        card_ids, deck_id = get_card_ids(conn, row['id'], return_deck_id=True)
        if not tags:
            tags = [''] # so ^$ will match

        # choosing targets to search in
        if only_tags:
            targets = tags
        elif only_field:
            fields = create_fields_dict(conn, row['mid'], row['flds'])
            targets = []
            # choosing only fields matching the desired pattern
            for key in fields.keys():
                if re.search(only_field, key, re.I):
                    targets.append(fields[key])
        else:
            # removing html tags
            flds = re.sub('<[^>]*>', '', row['flds']).split('\x1f')
            ids = [str(row['id']), str(row['mid'])]
            for card_id in card_ids:
                ids.append(str(card_id))
            ids.append(str(deck_id))
            targets = tags+ids+flds

        # searching
        groups = []
        for regex in regexps:
            found = False
            # searching fields, tags and ids for pattern
            for string in targets:
                r = re.search(regex, string, re.I)
                if r:
                    groups.append(r.group())
                    found = True
            # if one pattern failed to match, don't bother with the rest
            if not found:
                break

        # found will only be true if all patterns matched something
        if found:
            # printing only the id to stdout, so output can be piped somewhere
            if not human_readable:
                if not quiet:
                    print('Found ', ' and '.join(groups), ' in note ‘',
                          row['sfld'], '’, ', sep='', end='', file=sys.stderr)
                    if not cards:
                        print('note id:', file=sys.stderr)
                    else:
                        print('card ids:', file=sys.stderr)
                if not cards:
                    print(row['id'])
                else:
                    for card_id in card_ids:
                        print(card_id)
            else:
                if not cards:
                    print_note(conn, row['id'], row['mid'], row['flds'], row['tags'], cards=card_ids)
                else:
                    print_cards(conn, card_ids)
            success = True
    return success

def search_notes_field(conn, regexps):
    if not regexps:
        print('Usage: search_field field_regex regex [regex]...',
              file=sys.stderr)
        return False

    field_regex = regexps[0]
    regexps = regexps[1:]
    return search_notes(conn, regexps, only_field=field_regex)

def search_notes_fields(conn, regexps):
    if not regexps:
        print('Usage: search_fields_only regex [regex]...',
              file=sys.stderr)
        return False

    return search_notes(conn, regexps, only_field='.')

def search_notes_tags(conn, regexps):
    return search_notes(conn, regexps, only_tags=True)

def search_cards(conn, regexps):
    return search_notes(conn, regexps, cards=True)

models = None
def read_models(conn):
    global models
    if not models:
        row = conn.execute('select models from col where id=1').fetchone()
        if not row:
            raise Error("Couldn't read collection.")
        else:
            models = json.loads(row['models'])

collection_creation_date = None
def get_collection_creation_date(conn):
    global collection_creation_date
    if not collection_creation_date:
        row = conn.execute('select crt from col where id=1').fetchone()
        if not row:
            raise Error("Couldn't read collection.")
        else:
            try:
                collection_creation_date = datetime.datetime.fromtimestamp(row['crt']).date()
            except ValueError:
                raise Error("Couldn't understand collection's creation date: {}".format(row['crt']))
    return collection_creation_date

def create_fields_dict(conn, model_id, fieldsstr, reverse=None):
    global models
    if not models:
        read_models(conn)
    # creating fields dict
    fields = collections.OrderedDict()
    field_values = fieldsstr.split('\x1f')
    i = 0
    model_fields = models[str(model_id)]['flds']
    # reverse will be None if the note's fields should be presented as is
    # (including 'Reverse' field), or true or false if the fields should be
    # presented reversed or not
    # TODO: actually get regular and reversed layouts from model and print
    # accordingly
    if reverse:
        model_fields.reverse()
        field_values.reverse()
    for i in range(len(model_fields)):
        field = model_fields[i]
        if reverse != None and field['name'] == 'Reverse':
            continue
        if field_values and (i < len(field_values)):
            fields[field['name']] = field_values[i]
        else:
            fields[field['name']] = ''
    return fields

# These two functions are needed to communicate ordered dicts through json.
def ordered_dict_to_lists(dic):
    keys = []
    values = []
    for key in dic:
        keys.append(key)
        values.append(dic[key])
    return keys, values
def lists_to_ordered_dict(keys, values):
    r = collections.OrderedDict()
    for i in range(0, len(keys)):
        if i < len(values):
            r[keys[i]] = values[i]
        else:
            r[keys[i]] = ''
    return r

def print_fields(conn, note_id, model_id, fieldsstr, _json, print_notes=False, reverse=None):
    fields = create_fields_dict(conn, model_id, fieldsstr, reverse=reverse)
    # printing results
    if not _json:
        if not (quiet or print_notes):
            if not reverse:
                print('# Note {} #'.format(note_id), file=sys.stderr)
            else:
                print('# Note {} (reversed) #'.format(note_id), file=sys.stderr)
        for name in fields:
            # Strip html, replace </div> and <br>s with line breaks, since
            # that's how anki handles line breaks in fields
            field = re.sub('</div>|<br[^>]*>', '\n', fields[name]).rstrip()
            field = re.sub('<[^>]*>', '', field)
            if not quiet:
                print('## {} ##'.format(name), file=sys.stderr)
            print(field)
        if not print_notes:
            print()
        return None
    else:
        return ordered_dict_to_lists(fields)

def print_notes_fields(conn, ids, _json=False):
    notes = dict()
    success = False
    if not ids:
        if not quiet:
            print('Reading from stdin...', file=sys.stderr)
        ids = sys.stdin
    for _id in ids:
        _id = _id.rstrip()
        row = conn.execute('select mid,flds from notes where id=?',
                           (_id,)).fetchone()
        if not row:
            if not quiet:
                print('Note with id', _id, 'not found, skipping',
                      file=sys.stderr)
        else:
            success = True
            notes[_id] = print_fields(conn, _id, row['mid'], row['flds'],
                                      _json=_json)
                
    if _json:
        print(json.dumps(notes))
    return success

def dump_notes_fields(conn, ids):
    print_notes_fields(conn, ids, _json=True)

def replace_fields(conn, json_strings):
    total = 0
    if not json_strings:
        if not quiet:
            print('Reading from stdin...', file=sys.stderr)
        json_strings= sys.stdin
    for string in json_strings:
        notes = json.loads(string.rstrip())
        if type(notes) != dict:
            print('Malformed string, aborting:', string, file=sys.stderr)
            return False
        for _id in notes:
            note = notes[_id]
            if len(note) != 2 or type(note[0]) != list or type(note[1]) != list:
                print('Malformed string, aborting:', string, file=sys.stderr)
                return False
            fieldsstr = '\x1f'.join(note[1])
            conn.execute('update notes set flds=?,mod=?,usn=? where id=?',
                           (fieldsstr, int(time.time()), -1, _id))
            total += 1
    if total > 0:
        print(total, 'notes successfully modified')
    elif not quiet:
        print('No notes were modified', file=sys.stderr)
    return (total > 0)

def list_models_decks(conn, regexs, keyword):
    if keyword not in ['models', 'decks']:
        raise ValueError('Keyword should be either models or decks: '+keyword)

    if not regexs:
        if not quiet:
            print('Listing all ', keyword, '.', sep='', file=sys.stderr)
        regexs = ['.']

    row = conn.execute("select "+keyword+" from col where id=1").fetchone()
    if not row:
        print("Couldn't read collection.")
        return False

    try:
        dic = json.loads(row[keyword])
        if type(dic) != dict:
            raise ValueError
    except ValueError:
        print("Couldn't decode", keyword, "string:", row[keyword],
              file=sys.stderr)
        return False
    except IndexError:
        print("Couldn't find column", keyword, ":", row.keys(),
              file=sys.stderr)
        return False

    for key in dic:
        matches = True
        for regex in regexs:
            if (
                not re.search(regex, dic[key]['name'], re.I) and
                not re.search(regex, key, re.I)
               ):
                matches = False
                break
        if matches:
            if not quiet:
                print('# {} #'.format(dic[key]['name']), file=sys.stderr)
            print(key)
    return True

def list_models(conn, regexs):
    return list_models_decks(conn, regexs, 'models')

def list_decks(conn, regexs):
    return list_models_decks(conn, regexs, 'decks')

def print_tags(conn, note_id, tagsstr, print_notes=False):
    # printing results
    if not (quiet or print_notes):
        print('# Note {} #'.format(note_id), file=sys.stderr)
    print(tagsstr.strip())

def print_notes_tags(conn, ids, _json=False):
    notes = dict()
    success = False
    if not ids:
        if not quiet:
            print('Reading from stdin...', file=sys.stderr)
        ids = sys.stdin
    for _id in ids:
        _id = _id.rstrip()
        row = conn.execute('select tags from notes where id=?',
                           (_id,)).fetchone()
        if not row:
            if not quiet:
                print('Note with id', _id, 'not found, skipping',
                      file=sys.stderr)
        else:
            success = True
            if _json:
                notes[_id] = row['tags']
            else:
                print_tags(conn, _id, row['tags'])
                
    if _json:
        print(json.dumps(notes))
    return success

def dump_notes_tags(conn, ids):
    print_notes_tags(conn, ids, _json=True)

def replace_tags(conn, json_strings):
    total = 0
    if not json_strings:
        if not quiet:
            print('Reading from stdin...', file=sys.stderr)
        json_strings= sys.stdin
    for string in json_strings:
        notes = json.loads(string.rstrip())
        if type(notes) != dict:
            print('Malformed string, aborting:', string, file=sys.stderr)
            return False
        for _id in notes:
            tags = notes[_id].strip().split(' ')
            if not tags:
                tagsstr = ''
            else:
                tagsstr = ' {} '.format(' '.join(tags))
            conn.execute('update notes set tags=?,mod=?,usn=? where id=?',
                           (tagsstr, int(time.time()), -1, _id))
            total += 1
    if total > 0:
        print(total, 'notes successfully modified')
    elif not quiet:
        print('No notes were modified', file=sys.stderr)
    return (total > 0)

def print_note(conn, note_id, model_id, fields_str, tags_str, cards=None, reverse=None):
    if not quiet:
        if not reverse:
            print('# Note {} #'.format(note_id), file=sys.stderr)
        else:
            print('# Note {} (reversed) #'.format(note_id), file=sys.stderr)
    print_fields(conn, note_id, model_id, fields_str, _json=False, print_notes=True, reverse=reverse)
    if not quiet:
        print('## Tags ##', file=sys.stderr)
    print_tags(conn, note_id, tags_str, print_notes=True)
    if cards:
        if not quiet:
            print('## Cards ##', file=sys.stderr)
        for card_id in cards:
            print(card_id)
    print()

def print_notes(conn, ids, _json=False):
    success = False
    notes = {}
    if not ids:
        if not quiet:
            print('Reading from stdin...', file=sys.stderr)
        ids = sys.stdin
    for _id in ids:
        _id = _id.rstrip()
        row = conn.execute('select mid,flds,tags from notes where id=?',
                           (_id,)).fetchone()
        if not row:
            if not quiet:
                print('Note with id', _id, 'not found, skipping',
                      file=sys.stderr)
        else:
            success = True
            if not _json:
                print_note(conn, _id, row['mid'], row['flds'], row['tags'], cards=get_card_ids(conn, _id))
            else:
                fields = create_fields_dict(conn, row['mid'], row['flds'], reverse=False)
                notes[_id] = {
                        'model_id' : row['mid'],
                        'fields' : ordered_dict_to_lists(fields),
                        'tags' : row['tags'],
                        'cards' : get_card_ids(conn, _id),
                        }
    if _json:
        print(json.dumps(notes))
    return success

def dump_notes(conn, ids):
    return print_notes(conn, ids, _json=True)

def find_collection():
    default_locations = [
                         os.environ['HOME']+'/Anki/User 1/collection.anki2',
                         os.environ['HOME']+'/.anki/User 1/collection.anki2',
                         'collection.anki2'
                        ]
    for location in default_locations:
        if os.path.exists(location):
            return location
    return None

def prompt_confirmation():
    if quiet:
        return False
    print("\nWARNING: this software is alpha. Backup your collection "
          "before committing any changes. Check that everything went as "
          "expected before modifying the deck in anki (including reviewing "
          "cards), at the risk of having to restore your backup later and "
          "losing your work.\n",
          file=sys.stderr)
    try:
        answer = input('Commit changes (y/N)? ')
    except (EOFError, KeyboardInterrupt):
        answer = None
        print(file=sys.stderr)
    if answer == 'y' or answer == 'Y':
        return True
    return False

def print_card(conn, row, return_dict=False):
    if not row:
        return

    creation = get_collection_creation_date(conn)
    due_date = creation + datetime.timedelta(days=row['due'])
    interval = row['ivl']
    last_review = due_date - datetime.timedelta(days=interval)
    ease_factor = row['factor']/10
    reviews = row['reps']
    lapses = row['lapses']
    reverse = (row['ord'] == 1)
    note_id = row['nid']
    # id is unique
    note = conn.execute("select mid,flds,tags from notes where id = ?", (note_id,)).fetchone()

    if not return_dict:
        if not quiet:
            print('# Card {} #'.format(row['id']), file=sys.stderr)
        print('Due date: {}'.format(due_date))
        print('Interval: {} days'.format(interval))
        print('Last review: {}'.format(last_review))
        print('Ease factor: {}%'.format(ease_factor))
        print('Reviews: {}'.format(row['reps']))
        print('Lapses: {}'.format(row['lapses']))

        if note:
            print_note(conn, note_id, note['mid'], note['flds'], note['tags'], reverse=reverse)
    else:
        card_dict = {'due_date': str(due_date), 'interval': interval, 'last_review': str(last_review),
                       'ease_factor': ease_factor, 'reviews': reviews, 'lapses': lapses}
        fields = print_fields(conn, note_id, note['mid'], note['flds'], _json=True, reverse=reverse)
        note_dict = {note_id : {'fields': fields, 'tags': note['tags']}}
        card_dict['note'] = note_dict
        return card_dict

def print_cards(conn, ids, _json=False):
    success = True
    if not ids:
        if not quiet:
            print('Reading from stdin...', file=sys.stderr)
        ids = sys.stdin

    if _json:
        cards = collections.OrderedDict()

    for _id in ids:
        if isinstance(_id, str):
            try:
                _id = int(_id.strip())
            except ValueError:
                success = False
                continue
        # id is unique
        row = conn.execute("select id,nid,ord,due,ivl,factor,reps,lapses from cards where id = ?", (_id,)).fetchone()
        if row:
            if not _json:
                print_card(conn, row, return_dict=False)
            else:
                cards[_id] =  print_card(conn, row, return_dict=True)
        elif not quiet:
            print('Card with id', _id, 'not found, skipping',
                  file=sys.stderr)
            success = False

    if _json:
        print(json.dumps(cards))
    return success

def dump_cards(conn, ids):
    return print_cards(conn, ids, _json=True)


quiet = False
human_readable = False
def run():
    global quiet
    global human_readable

    # command line command -> handler function
    commands = {
        'dump_fields': dump_notes_fields,
        'dump_tags': dump_notes_tags,
        'dump_notes': dump_notes,
        'list_decks': list_decks,
        'list_models': list_models,
        'mv_tags': rename_tags,
        'print_notes': print_notes,
        'print_fields': print_notes_fields,
        'print_tags': print_notes_tags,
        'replace_fields': replace_fields,
        'replace_tags': replace_tags,
        'rm_tags': remove_tags,
        'search': search_notes,
        'search_field': search_notes_field,
        'search_fields_only': search_notes_fields,
        'search_tags': search_notes_tags,
        'search_cards': search_cards,
        'print_cards': print_cards,
        'dump_cards': dump_cards,
        }

    # parsing command line
    parser = argparse.ArgumentParser(description='Low level manipulation of '
                                                 'anki collections')
    parser.add_argument('-f', '--force', dest='force', action='store_true',
                        help='force committing changes to database')
    parser.add_argument('-q', '--quiet', dest='quiet', action='store_true',
                        help="don't print helpful messages to stderr (error "
                             "messages are still printed)")
    parser.add_argument('-r', '--human-readable', dest='human_readable',
                        action='store_true', help="search functions will print "
                        "human readable output (equivalent to piping to the "
                        "appropriate print_* funcition)")
    parser.add_argument('-c', '--collection', dest='db',
                        metavar='collection_db',
                        help='collection database file')
    parser.add_argument('command', choices=sorted(commands.keys()),
                        help='command to execute')
    parser.add_argument('arguments', nargs='*',
                        help='arguments for the command')
    opts = parser.parse_args()

    if opts.quiet:
        quiet = True

    if opts.human_readable:
        human_readable = True

    if opts.db:
        collection = opts.db
        if not os.path.exists(collection):
            print("Error: couldn't find collection at ‘", collection, '’.',
                  sep='', file=sys.stderr)
            exit(1)
    else:
        collection = find_collection()
        if not collection:
            print("Error: couldn't find collection. Try specifying its", 
                  "location with -c.", file=sys.stderr)
            exit(1)

    # connecting to the database
    connection = sqlite3.connect(collection)
    connection.row_factory = sqlite3.Row

    # executing
    try:
        success = commands[opts.command](connection, opts.arguments)
    except KeyboardInterrupt:
        success = False

    # committing transactions
    if success and connection.in_transaction:
        if opts.force or prompt_confirmation():
            connection.commit()
        else:
            print('\nCanceling changes. Your collection was not modified.',
                  '(If piping to stdin or using -q, use the -f switch to force '
                  'committing.)',
                  sep='\n', file=sys.stderr)
            success = False

    # cleaning up
    connection.close()
    if success:
        exit(0)
    else:
        exit(2)

# Only run if being executed directly, so other scripts can source this one and
# call its functions. Note that, in this case, the caller is responsible for
# opening and closing the database and committing any changes.
if os.path.splitext(os.path.basename(sys.argv[0]))[0] == 'anki_tool':
    run()
