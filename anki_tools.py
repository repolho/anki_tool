#! /usr/bin/python3
print("WARNING: this software is alpha. Don't use it on an unbacked-up collection, at the risk of corrupting it and losing your data.", end='\n\n')

# TODO: add cards, search cards, rename tag, remove tags from cards and not only
# from the tags list (i.e. remove non-empty tags)

import sys
import os
import sqlite3
import re

def get_index(target, value):
    for i in range(0, len(target)):
        if target[i] == value:
            return i
    return None

def remove_tags(cursor, tags):
    cursor.execute("select * from col")
    row = cursor.fetchone()

    i = get_index(row.keys(), "tags") # for building the new tuple
    if i == None:
        print("Couldn't find column ‘tags’ in table ‘col’", file=sys.stderr)
        return False

    tagstr = row[i]
    n = 0
    for tag in tags:
        if re.search('"{}": -1'.format(tag), tagstr) == None:
            print("Couldn't find tag ‘{}’, ignoring".format(tag), file=sys.stderr)
        else: # '{"tag": -1, "tag": -1, "tag": -1}' -> '{"tag": -1, "tag": -1}'
            n += 1
            # removes tag, but leaves extra comma
            tagstr = re.sub('"{}": -1'.format(tag), "", tagstr)
            # removes extra comma for middle or final tag
            tagstr = re.sub(", (, |})", r"\1", tagstr)
            # removes extra comma for initial tag
            tagstr = re.sub("{, ", "{", tagstr)

    if n == 0:
        print("No tags were removed", file=sys.stderr)
        return False

    newtuple = tuple(row)[:i]+(tagstr,)+tuple(row)[i+1:]
    # template should be "... values (?,?,?,...,?)" with as many "?" as there
    # are items in the tuple; the [:-1] is meant to remove the last comma
    templatestr = "insert or replace into col values ("+("?,"*len(row))[:-1]+")"

    try:
        cursor.execute(templatestr, newtuple)
    except sqlite3.OperationalError:
        print("Couldn't execute transaction because database is locked. Quit anki and try again.", file=sys.stderr)
        return False

    if cursor.rowcount <= 0:
        print("Error replacing row in database", file=sys.stderr)
        return False
    else:
        print("{} tag(s) successfully removed".format(n))

    return True

# command line command -> handler function
commands = dict({
    "rm_tags": remove_tags
    })

# Handling errors is command line
if len(sys.argv) < 4 or not os.path.exists(sys.argv[1]) or sys.argv[2] not in commands.keys():
    if len(sys.argv) >= 2 and not os.path.exists(sys.argv[1]):
        print("File not found:", sys.argv[1], file=sys.stderr)
    if len(sys.argv) >= 3 and sys.argv[2] not in commands.keys():
        print("Unknown command:", sys.argv[2], file=sys.stderr)
    print("Usage: {} anki_collection_file command arguments\n  Available commands: {}".format(sys.argv[0], " ".join(commands.keys())), file=sys.stderr)
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
