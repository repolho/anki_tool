#! /usr/bin/python3

import sys
import os
import os.path
import sqlite3
import re
import json
import time
import collections

def rename_tag_in_cards(cursor, tag, dst):
    """Renames a single tag in all cards"""
    n = 0
    cursor.execute("select * from notes where tags like ?",
                   ('%'+tag+'%',))
    found = []
    for row in cursor:
        tags = row['tags'].split()
        # Searching again because sql will return tags containing the tag we're
        # looking for, e.g. if src is 'a', sql will return 'a', 'ab', etc. We
        # will only rename the exact match
        if tag in tags:
            found.append(dict(row))

    for row in found:
        tags = row['tags'].split()
        tags.remove(tag)
        if dst != None:
            tags.append(dst)
        # remove duplicates and sort
        tags = sorted(set(tags))
        if not tags:
            tagstr = ''
        else:
            tagstr = ' {} '.format(' '.join(tags))
        cursor.execute('update notes set tags=?,mod=?,usn=? where id=?',
                       (tagstr, int(time.time()), -1, row['id']))
        n += 1

    if n > 0:
        if dst != None:
            verb = 'renamed'
        else:
            verb = 'removed'
        print('Tag ‘'+tag+'’ successfully', verb, 'in',
               n, 'cards.', file=sys.stderr)
    else:
        print('Tag ‘'+tag+'’ not found in any cards.', file=sys.stderr)

def rename_tags(cursor, tags, remove=False):
    """Renames or removes all tags matching regular expressions"""

    if not remove and len(tags) < 2:
        print('Usage: mv_tags regex [regex]... destination',
              file=sys.stderr)
        return False
    elif remove and not tags:
        tags = []
        for tag in sys.stdin:
            tags.append(tag.rstrip())

    if not remove:
        dst = tags[-1]
        srcs = tags[:-1]
    else:
        dst = None
        srcs = tags

    cursor.execute("select * from col where id=1")
    row = cursor.fetchone()
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
            if re.search(target, tag) != None:
                found = True
                n += 1
                del tagsdict[tag]
                if dst != None:
                    tagsdict[dst] = -1

                try:
                    rename_tag_in_cards(cursor, tag, dst)
                except sqlite3.OperationalError:
                    return False
        if not found:
            print("Couldn't find tags matching ‘{}’, searching cards for exact "
                  "string.".format(target), file=sys.stderr)
            try:
                rename_tag_in_cards(cursor, target, dst)
            except sqlite3.OperationalError:
                return False

    tagstr = json.dumps(tagsdict)
    cursor.execute('update col set tags=?,mod=? where id=?',
                   (tagstr, int(time.time()*1000), row['id']))

    if not remove:
        verb = 'renamed'
    else:
        verb = 'removed'
    if n == 0:
        print('No tags were', verb, file=sys.stderr)
        return False
    else:
        print(n, 'tag(s) successfully', verb, file=sys.stderr)

    return True

def remove_tags(cursor, tags):
    return rename_tags(cursor, tags, remove=True)

def search_cards(cursor, regexps):
    if not regexps:
        regexps = []
        for regex in sys.stdin:
            regexps.append(regex.rstrip())

    success = False
    cursor.execute('select id,mid,flds,tags,sfld from notes')
    for row in cursor:
        tags = row['tags'].split()
        ids = [str(row['id']), str(row['mid'])]
        groups = []
        for regex in regexps:
            found = False
            # searching fields, tags and ids for pattern
            for string in tags+ids+[row['flds']]:
                r = re.search(regex, string)
                if r != None:
                    groups.append(r.group())
                    found = True
            # if one pattern failed to match, don't bother with the rest
            if not found:
                break
        # found will only be true if all patterns matched something
        if found:
            # printing only the id to stdout, so output can be piped somewhere
            print('Found '+' and '.join(groups)+' in card ‘'+row['sfld']+'’, id:',
                  file=sys.stderr)
            print(row['id'])
            success = True
    return success

models = None
def read_models(cursor):
    global models
    if not models:
        cursor.execute('select models from col where id=1')
        row = cursor.fetchone()
        if not row:
            raise Error("Couldn't read collection.")
        else:
            models = json.loads(row['models'])

def create_fields_dict(cursor, model_id, fieldsstr):
    if not models:
        read_models(cursor)
    # creating fields dict
    fields = collections.OrderedDict()
    field_values = fieldsstr.split('\x1f')
    i = 0
    for field in models[str(model_id)]['flds']:
        if i < len(field_values):
            fields[field['name']] = field_values[i]
            i += 1
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

def print_fields(cursor, note_id, model_id, fieldsstr, _json):
    fields = create_fields_dict(cursor, model_id, fieldsstr)
    # printing results
    if not _json:
        print('# Card {} #'.format(note_id), file=sys.stderr)
        for name in fields:
            print('## {} ##'.format(name), file=sys.stderr)
            print(fields[name])
        print()
    else:
        card = {note_id: ordered_dict_to_lists(fields)}
        print(json.dumps(card))

def print_cards_fields(cursor, ids, _json=False):
    success = False
    if not ids:
        ids = sys.stdin
    for _id in ids:
        _id = _id.rstrip()
        cursor.execute('select mid,flds from notes where id=?', (_id,))
        row = cursor.fetchone()
        if not row:
            print('Card with id', _id, 'not found, skipping', file=sys.stderr)
        else:
            success = True
            print_fields(cursor, _id, row['mid'], row['flds'], _json=_json)
    return success

def dump_cards_fields(cursor, ids):
    print_cards_fields(cursor, ids, _json=True)

def replace_fields(cursor, json_strings):
    success = False
    for string in json_strings:
        cards = json.loads(string)
        if type(cards) != dict:
            print('Malformed string, aborting:', string, file=sys.stderr)
            return False
        for _id in cards:
            card = cards[_id]
            if len(card) != 2 or type(card[0]) != list or type(card[1]) != list:
                print('Malformed string, aborting:', string, file=sys.stderr)
                return False
            fieldsstr = '\x1f'.join(card[1])
            cursor.execute('update notes set flds=?,mod=?,usn=? where id=?',
                           (fieldsstr, int(time.time()), -1, _id))
            success = True
    return success

def run():
    # command line command -> handler function
    commands = {
        'rm_tags': remove_tags,
        'mv_tags': rename_tags,
        'search': search_cards,
        'print_fields': print_cards_fields,
        'dump_fields': dump_cards_fields,
        'replace_fields': replace_fields
        }

    # handling errors in command line
    if len(sys.argv) < 3 or not os.path.exists(sys.argv[1]) or sys.argv[2] not in commands.keys():
        if len(sys.argv) >= 2 and not os.path.exists(sys.argv[1]):
            print("File not found:", sys.argv[1], file=sys.stderr)
        if len(sys.argv) >= 3 and sys.argv[2] not in commands.keys():
            print("Unknown command:", sys.argv[2], file=sys.stderr)
        print("Usage: {} anki_collection_file command arguments\n"
              "Available commands: {}".format(sys.argv[0],
                                              " ".join(commands.keys())),
              file=sys.stderr)
        exit(1)

    collection = sys.argv[1]
    command = sys.argv[2]
    args = sys.argv[3:]

    # connecting to the database
    connection = sqlite3.connect(collection)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    # executing and committing transactions
    success = commands[command](cursor, args)
    if success and connection.in_transaction:
        print("\nWARNING: this software is alpha. Backup your collection "
              "before committing any changes. Check that everything went as "
              "expected before modifying the deck in anki (including reviewing "
              "cards), at the risk of having to restore your backup later and "
              "losing your changes.\n",
              file=sys.stderr)
        try:
            answer = input('Commit changes (y/N)? ')
        except (EOFError, KeyboardInterrupt):
            answer = None
        if answer == 'y' or answer == 'Y':
            connection.commit()
        else:
            print('\nCanceling changes, your deck was not modified.',
                  file=sys.stderr)
            success = False

    # cleaning up
    cursor.close()
    connection.close()
    if success:
        exit(0)
    else:
        exit(2)

# Only run if being executed directly, so other scripts can source this one and
# call its functions. Note that, in this case, the caller is responsible for
# opening and closing the database and commiting any changes.
if os.path.splitext(os.path.basename(sys.argv[0]))[0] == 'anki_tools':
    run()
