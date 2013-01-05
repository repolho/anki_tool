#! /usr/bin/python3

# TODO: add cards, expand options for searching cards (e.g. searching for card
# type)

import sys
import os
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
        print('tag ‘'+tag+'’ successfully', verb, 'in',
               n, 'cards', file=sys.stderr)
    else:
        print('tag ‘'+tag+'’ not found in any cards', file=sys.stderr)

def rename_tags(cursor, args, remove=False):
    """Renames or removes all tags matching regular expressions"""

    if not remove and len(args) < 2:
        print('Usage: mv_args regex [regex]... destination',
              file=sys.stderr)
        return False
    elif remove and len(args) == 0:
        print('Usage: rm_args regex [regex]...',
              file=sys.stderr)
        return False
    if not remove:
        dst = args[-1]
        srcs = args[:-1]
    else:
        dst = None
        srcs = args

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
            print("Couldn't find tags matching ‘{}’, ignoring".format(target),
                  file=sys.stderr)

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
    success = False
    cursor.execute('select id,flds,tags,sfld from notes')
    for row in cursor:
        groups = []
        found = True
        for regex in regexps:
            r = re.search(regex, row['flds']+row['tags'])
            if r != None:
                groups.append(r.group())
            else:
                found = False
                break
        if found:
            # printing only the id to stdout, so output can be piped somewhere
            print('found '+' and '.join(groups)+' in card ‘'+row['sfld']+'’, id:',
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

def print_fields(cursor, model_id, fieldsstr, _json):
    fields = create_fields_dict(cursor, model_id, fieldsstr)
    # printing results
    if not _json:
        for name in fields:
            print('## {} ##'.format(name), file=sys.stderr)
            print(fields[name])
    else:
        print(json.dumps(fields))

def print_cards_fields(cursor, ids, _json=False):
    success = False
    for _id in ids:
        cursor.execute('select mid,flds from notes where id=?', (_id,))
        row = cursor.fetchone()
        if not row:
            print('Card with id', _id, 'not found, skipping', file=sys.stderr)
        else:
            success = True
            if not _json:
                print('# Card {} #'.format(_id), file=sys.stderr)
            print_fields(cursor, row['mid'], row['flds'], _json=_json)
    return success

def dump_cards_fields(cursor, ids):
    print_cards_fields(cursor, ids, _json=True)

# command line command -> handler function
commands = dict({
    'rm_tags': remove_tags,
    'mv_tags': rename_tags,
    'search': search_cards,
    'print_fields': print_cards_fields,
    'dump_fields': dump_cards_fields
    })

# handling errors in command line
if len(sys.argv) < 4 or not os.path.exists(sys.argv[1]) or sys.argv[2] not in commands.keys():
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
    print("\nWARNING: this software is alpha. Backup your collection before",
          "committing any changes. Check that everything went as expected before",
          "modifying the deck in anki (including reviewing cards), at the risk of",
          "having to restore your backup later and losing your changes.\n",
          file=sys.stderr)
    answer = input('Commit changes (y/N)? ')
    if answer == 'y' or answer == 'Y':
        connection.commit()
    else:
        print('Canceling changes, your deck was not modified', file=sys.stderr)
        success = False

# cleaning up
cursor.close()
connection.close()
if success:
    exit(0)
else:
    exit(2)
