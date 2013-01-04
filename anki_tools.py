#! /usr/bin/python3

# TODO: add cards, expand options for searching cards (e.g. searching for card
# type)

import sys
import os
import sqlite3
import re
import ast
import time

def get_index(target, value):
    for i in range(0, len(target)):
        if target[i] == value:
            return i
    return None

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
        cursor.execute('update notes set tags=?,mod=? where id=?',
                       (tagstr, int(time.time()), row['id']))
        n += 1

    if n > 0:
        if dst != None:
            verb = 'renamed'
        else:
            verb = 'removed'
        print('tag ‘'+tag+'’ successfully', verb, 'in',
               n, 'cards')
    else:
        print('tag ‘'+tag+'’ not found in any cards')

def rename_tags(cursor, args, remove=False):
    """Renames or removes all args matching regular expressions"""

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

    try:
        # format is {"tag1": -1, "tag2": -1}
        tagsdict = ast.literal_eval(row['tags'])
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

    tagstr = str(tagsdict).replace("'", '"')
    cursor.execute('update col set tags=?,mod=? where id=?',
                   (tagstr, int(time.time()), row['id']))

    if not remove:
        verb = 'renamed'
    else:
        verb = 'removed'
    if n == 0:
        print('No tags were', verb, file=sys.stderr)
        return False
    else:
        print(n, 'tag(s) successfully', verb)

    return True

def remove_tags(cursor, tags):
    return rename_tags(cursor, tags, remove=True)

def search_cards(cursor, regexps):
    success = False
    for regex in regexps:
        cursor.execute('select flds,tags,sfld from notes')
        for row in cursor:
            r = re.search(regex, row['flds']+row['tags'])
            if r != None:

                print('found ‘'+r.group()+'’ in card ‘'+row['sfld']+'’')
                success = True
    return success

# command line command -> handler function
commands = dict({
    'rm_tags': remove_tags,
    'mv_tags': rename_tags,
    'search': search_cards 
    })

# Handling errors is command line
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
          "commiting any changes. Check that everything went as expected before",
          "modifying the deck in anki (including reviewing cards), at the risk of",
          "having to restore your backup and losing your changes.\n",
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
