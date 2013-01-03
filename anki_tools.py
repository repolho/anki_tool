#! /usr/bin/python3
print("WARNING: this software is alpha. Don't use it on an unbacked-up collection, at the risk of corrupting it and losing your data.", end='\n\n')

# TODO: add cards, search cards

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

def replace_field(cursor, row, field_number, newstr):
    newtuple = tuple(row)[:field_number]+(tagstr,)+tuple(row)[field_number+1:]
    # template should be "... values (?,?,?,...,?)" with as many "?" as there
    # are items in the tuple; the [:-1] is meant to remove the last comma
    templatestr = "insert or replace into col values ("+("?,"*len(row))[:-1]+")"

    try:
        cursor.execute(templatestr, newtuple)
    except sqlite3.OperationalError:
        print("Couldn't execute transaction because database is locked.",
              "Quit anki and try again.", sep='\n', file=sys.stderr)
        raise

def rename_tag_in_cards(cursor, regex, dst):
    # for building the new tuple
    i = -1
    cursor.execute("select * from notes")
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
        replaced = False
        for j in range(0, len(tags)):
            if re.search(regex, tags[j]) != None:
                if dst == None or dst in tags:
                    del tags[j]
                else:
                    tags[j] = dst
                replaced = True
        if replaced:
            tagstr = ' '.join(tags)
            try:
                replace_field(cursor, row, i, tagstr)
            except sqlite3.OperationalError:
                raise

def rename_tags(cursor, tags, remove=False):
    """Renames or removes all tags matching regular expressions"""

    if not remove and len(tags) < 2:
        print('Usage: mv_tags regex [regex]... destination',
              file=sys.stderr)
        return False
    elif remove and len(tags) == 0:
            print('Usage: rm_tags regex [regex]...',
                  file=sys.stderr)
        return False
    if not remove:
        dst = tags[-1]
        srcs = tags[:-1]
    else:
        dst = None
        srcs = tags

    cursor.execute("select * from col")
    row = cursor.fetchone()

    # for building the new tuple
    i = get_index(row.keys(), "tags")
    if i == None:
        print("Couldn't find column ‘tags’ in table ‘col’", file=sys.stderr)
        return False

    # dict({"tag1": -1, "tag2": -1})
    try:
        return ast.literal_eval(row[0])
    except ValueError:
        print("Couldn't decode tags string:", row[0], file=sys.stderr)
        return False

    n = 0
    for target in srcs:
        found = False
        for tag in tagsdict:
            if re.search(target, tag):
                found = True
                n += 1
                del tagsdict[target]
                if dst != None and dst not in tagsdict:
                    tagsdict[dst] = -1

                try:
                    rename_tag_in_cards(cursor, target, dst)
                except sqlite3.OperationalError:
                    return False
        if not found:
            print("Couldn't find tags matching ‘{}’, ignoring".format(target),
                  file=sys.stderr)

    if n == 0:
        if not remove:
            print('No tags were renamed', file=sys.stderr)
        else:
            print('No tags were removed', file=sys.stderr)
        return False

    tagstr = str(tagsdict).replace("'", '"')
    try:
        replace_field(cursor, row, i, tagstr)
    except sqlite3.OperationalError:
        return False

    if cursor.rowcount <= 0:
        print("Error replacing row in database", file=sys.stderr)
        return False
    else:
        print("{} tag(s) successfully renamed".format(n))

    return True

def remove_tags(cursor, tags):
    rename_tags(cursor, tags, remove=True)

# command line command -> handler function
commands = dict({
    'rm_tags': remove_tags,
    'mv_tags': rename_tags
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
if success:
    connection.commit()

# cleaning up
cursor.close()
connection.close()
if success:
    exit(0)
else:
    exit(2)
