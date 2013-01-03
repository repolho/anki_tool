#! /usr/bin/python3
print("WARNING: this software is alpha. Don't use it on an unbacked-up collection, at the risk of corrupting it and losing your data.", end='\n\n')

# TODO: add cards, expand options for searching cards (e.g. searching for card
# type)

import sys
import os
import sqlite3
import re
import ast

def get_index(target, value):
    for i in range(0, len(target)):
        if target[i] == value:
            return i
    return None

def replace_field(cursor, table, row, field_number, newstr):
    newtuple = tuple(row)[:field_number]+(newstr,)+tuple(row)[field_number+1:]
    # template should be "... values (?,?,?,...,?)" with as many "?" as there
    # are items in the tuple; the [:-1] is meant to remove the last comma
    templatestr = ("insert or replace into "+table+
                   " values ("+("?,"*len(row))[:-1]+")")

    try:
        cursor.execute(templatestr, newtuple)
    except sqlite3.OperationalError:
        print("Couldn't execute transaction. Is the database locked?",
              file=sys.stderr)
        raise

def rename_tag_in_cards(cursor, tag, dst):
    """Renames a single tag in all cards"""
    # for building the new tuple
    i = -1
    n = 0
    cursor.execute("select * from notes where tags like '%{}%'".format(tag))
    found = []
    for row in cursor:
        if i == -1:
            i = get_index(row.keys(), "tags")
            if i == None:
                print("Couldn't find column ‘tags’ in table ‘notes’",
                      file=sys.stderr)
                return False

        tags = row[i].split()
        # Searching again because sql will return tags containing the tag we're
        # looking for, e.g. if src is 'a', sql will return 'a', 'ab', etc. We
        # will only rename the exact match
        if tag in tags:
            found.append(list(row))

    for row in found:
        tags = row[i].split()
        replaced = False
        for j in range(0, len(tags)):
            if tag == tags[j]:
                n += 1
                if dst == None or dst in tags:
                    del tags[j]
                else:
                    tags[j] = dst
                replaced = True
        if replaced:
            tagstr = ' '+' '.join(tags)+' '
            try:
                replace_field(cursor, 'notes', row, i, tagstr)
            except sqlite3.OperationalError:
                raise

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

    cursor.execute("select * from col")
    row = cursor.fetchone()

    # for building the new tuple
    i = get_index(row.keys(), "tags")
    if i == None:
        print("Couldn't find column ‘tags’ in table ‘col’", file=sys.stderr)
        return False

    # dict({"tag1": -1, "tag2": -1})
    try:
        tagsdict = ast.literal_eval(row[i])
    except ValueError:
        print("Couldn't decode tags string:", row[i], file=sys.stderr)
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
                if dst != None and dst not in tagsdict:
                    tagsdict[dst] = -1

                try:
                    rename_tag_in_cards(cursor, tag, dst)
                except sqlite3.OperationalError:
                    return False
        if not found:
            print("Couldn't find tags matching ‘{}’, ignoring".format(target),
                  file=sys.stderr)

    tagstr = str(tagsdict).replace("'", '"')
    try:
        replace_field(cursor, 'col', row, i, tagstr)
    except sqlite3.OperationalError:
        return False

    if n == 0:
        if not remove:
            print('No tags were renamed', file=sys.stderr)
        else:
            print('No tags were removed', file=sys.stderr)
        return False
    else:
        print("{} tag(s) successfully renamed".format(n))

    return True

def remove_tags(cursor, tags):
    rename_tags(cursor, tags, remove=True)

def search_cards(cursor, regexps):
    success = False
    for regex in regexps:
        cursor.execute('select flds,tags,sfld from notes')
        for row in cursor:
            r = re.search(regex, row[0]+row[1])
            if r != None:
                print('found ‘'+r.group()+'’ in card ‘'+row[2]+'’')
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
    connection.commit()

# cleaning up
cursor.close()
connection.close()
if success:
    exit(0)
else:
    exit(2)
