#! /usr/bin/python3
"""Add audio to notes lacking it. This is an example of how to manipulate notes' fields using anki_tool, which you can use as a base for your own application.
Usage: anki_tool -q search . | anki_tool -q dump_fields | ./example_field_modifier.py | anki_tool -f replace_fields"""

import sys
import json
import re
import anki_tool

modified_notes = dict()
# reading json produced by dump_fields from stdin
for line in sys.stdin:
    notes = json.loads(line.rstrip())
    # getting back the original dict for each note
    for _id in notes:
        keys, values = notes[_id]
        notes[_id] = anki_tool.lists_to_ordered_dict(keys, values)

    for _id in notes:
        note = notes[_id]
        # if the note does not already contain audio
        if ('Front' in note and 
            not re.search(r'\[sound:[^\]+]', note['Front'])):

            # getting first word in the field
            word = re.search(r'^\w+', note['Front']).group()
            # adding audio for that word
            note['Front'] += '<div>[sound:'+word+'.mp3]</div>'

            modified_notes[_id] = note

# prepare notes for output, replacing dict with lists so we don't lose the field
# order
for _id in modified_notes:
    modified_notes[_id] = anki_tool.ordered_dict_to_lists(modified_notes[_id])

# also print our modification in a human-readable way
for _id in modified_notes:
    print(_id, modified_notes[_id], file=sys.stderr)

# print result, which can be fed to replace_fields
print(json.dumps(modified_notes))
