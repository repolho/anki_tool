anki_tool
==========

Anki_tool is a program providing low level access to Anki 2 collections. It's main purpose is to provide better searching and to automate tasks that must otherwise be performed manually in Anki.

All commands requiring regular expression will be forwarding them unchanged to python's [re module](http://docs.python.org/3/library/re.html), therefore the syntax must be the one used by that module.

## Available commands: ##

### search ###

    Usage: anki_tool search regex [regex]...

Search all notes in collection for one or more regex patterns and print the note ids of matching notes to stdout. The patterns can be optionally provided through stdin instead of the command line. They are matched against the note's fields, tags, id and card model id. Card model ids can be discovered with the list_models command. For searching only in one or more fields, use search_field, and for searching only the note's tags, use search_tag.

This command's output can be piped into any command expecting note ids, namely print_fields, print_tags, dump_fields and dump_tags.

For example, to search for all notes with a model id of 1360787441567, containing the word "red" (but not "credibility") and tagged "color," and print those notes' fields to stdout, one might use:

    $ anki_tool search 1360787441567 '\bred\b' '^color$' | anki_tool print_fields

One might also use the list_models command to obtain the model id of the model named "Basic:"

    $ anki_tool search $(anki_tool -q list_models '^Basic$') '\bred\b' '^color$' | anki_tool print_fields

### search_field ###

    Usage: anki_tool search_field field_regex regex [regex]...

Search all fields whose names match field_regex for one or more patterns and print the note ids of matching notes to stdout. The search patterns can be provided through stdin, but not the field pattern, which must be provided in the command line.

This command's output can be piped into any command expecting note ids, namely print_fields, print_tags, dump_fields and dump_tags.

For example, to search for all notes containing the word "car" in the fields named "Front" or "Back" (but not "Obs"), one might use:

    $ anki_tool search_field '^(Front|Back)$' '\bcar\b'

### search_fields_only ###

    Usage: anki_tool search_fields_only regex [regex]...

Search all fields, but not tags and ids, for one or more patterns and print the note ids of matching notes to stdout. The search patterns can be provided through stdin, but not the field pattern, which must be provided in the command line. This command is equivalent to using search_field and a field regex that will match every field.

This command's output can be piped into any command expecting note ids, namely print_fields, print_tags, dump_fields and dump_tags.

For example, to search for all notes containing the word "color" in a field, but not in a tag, you can use:

    $ anki_tool search_fields_only '\bcolor\b'

note that this is equivalent to:

    $ anki_tool search_field '.' '\bcolor\b'

### search_tags ###

    Usage: anki_tool search_tags regex [regex]...

Search tags in all notes for one or more patterns and print the note ids of matching notes to stdout. The patterns can be optionally provided through stdin instead of the command line.

This command's output can be piped into any command expecting note ids, namely print_fields, print_tags, dump_fields and dump_tags.

For example, to search for all notes tagged "bird," but not the note whose "Front" field reads "bird," one might use:

    $ anki_tool search_tags '^bird$'

### list_decks ###

    Usage: anki_tool list_decks [regex]...

List all deck ids for decks matching one or more patterns. If no patterns are specified, '.' is assumed (i.e. all decks are listed).

For example, to list the deck id from the deck "Default," one might use:

    $ anki_tool list_decks '^Default$'

### list_models ###

    Usage: anki_tool list_models [regex]...

List all model ids for models matching one or more patterns. If no patterns are specified, '.' is assumed (i.e. all models are listed).

For example, to list the model id from the model "Basic," one might use:

    $ anki_tool list_models '^Basic$'

### rm_tags ###

    Usage: anki_tool rm_tags regex [regex]...

Remove all tags matching one or more patterns. The patterns may optionally be passed to stdin instead of the command line.

For example, to remove all tags ending in "101," one might use:

    $ anki_tool rm_tags '101$'

### mv_tags ###

    Usage: anki_tool mv_tags regex [regex]... destination

Rename all tags matching one or more patterns. At least one pattern and the destination must necessarily be passed through the command line. 

For example, to rename the tags "dinosaur" and "mammal" into "animal," one might use:

    $ anki_tool mv_tags '(dinosaur|mammal)' animal

### print_fields ###

    Usage: anki_tool print_fields note_id [note_id]...

Print all fields from the specified notes. The note ids may be optionally passed through stdin instead of the command line. This command is useful for visualizing the search results produced by the search, search_fields or search_tags commands.

Note that any html will be stripped from the fields prior to printing. To see the fields' exact content, use dump_fields instead.

For example, to print all fields from all notes containing the word "date," one might use:

    $ anki_tool -q search '\bdate\b' | anki_tool print_fields

### dump_fields ###
### replace_fields###

    Usage: anki_tool dump_fields note_id [note_id]...
    Usage: anki_tool replace_fields note_json [note_json]...

Print a json representation of all fields from the specified notes, or modify notes based on a json representation of those notes' fields. The note ids or json representations may be optionally passed through stdin instead of the command line. These command are more useful when used in combination with each other.

For example, to replace the word "Britain" with the word "UK" in all fields in all notes, one might use:

    $ anki_tool -q search '\bBritain\b' | anki_tool -q dump_fields | \
        sed 's/Britain/UK/g' | anki_tool -f replace_fields

For more complex modifications, it is recommended that the user write a small program to actually parse the json outputted by dump_fields, modify it in the desired way, and then perform a new json dump and feed it into replace_fields. See the example_field_modifier.py for a python sample of such a program.

### print_tags ###

    Usage: anki_tool print_tags note_id [note_id]...

Print all tags from the specified notes. The note ids may be optionally passed through stdin instead of the command line. This command is more useful when used in combination with one of the search commands.

For example, to print all tags from all notes containing the tag "sport," one might use:

    $ anki_tool -q search_tags '^sport$' | anki_tool print_tags

### dump_tags ###
### replace_tags###

    Usage: anki_tool dump_tags note_id [note_id]...
    Usage: anki_tool replace_tags note_json [note_json]...

Print a json representation of all tags from the specified notes, or modify notes based on a json representation of those notes' tags. The note ids or json representations may be optionally passed through stdin instead of the command line. These command are more useful when used in combination with each other.

For example, to replace the tag "fish" with the tag "mammal" in all notes containing the word "whale," one might use:

    $ anki_tool -q search '\bwhale\b' | anki_tool -q dump_tags | \
        sed 's/fish/mammal/g' | anki_tool -f replace_tags

### print_notes ###

    Usage: anki_tool print_notes note_id [note_id]...

Print all fields and tags from the specified notes. The note ids may be optionally passed through stdin instead of the command line. This command is useful for visualizing the search results produced by the search, search_fields or search_tags commands.

Note that any html will be stripped from the fields prior to printing. To see the fields' exact content, use dump_fields instead.

For example, to print all notes containing the word "word," one might use:

    $ anki_tool -q search '\bword\b' | anki_tool print_notes
