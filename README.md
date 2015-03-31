# Sublime Text FoldConditions Package adding code folding for C/C++ conditinoal compile directives.

## Install

    $ https://github.com/GuyCarver/FoldConditions

## Instructions

This package allows you to set a number of values as defined then fold the source file conditional compile directives based on those defines.

### Key Bindings:

* ctrl+k, d = Toggle define of the word under the cursor.
* ctrl+k, D = Set current selected region as limit for folding.  This doesn't work well if you miss a condition in your selection.
* ctrl+k, n = Undefine the word under the cursor.
* ctrl+k, l = List defines and remove selected
* ctrl+m = Find matching condition line of condition under the cursor.
* ctrl+k, ctrl+d = Fold file with current define list.

#### Known Issues:
* The c.tmLanguage file doesn't correctly tag #endif lines if the #if or #ifdef spans a funciton start but not the function end.  These lines will be white rather than the color you have set for preprocessor definitions.  I've patched these holes by manually searching the file for them.
* The Find match only goes up for #else and #elif conditions to find the matching #if #ifdef at the moment.  You cannot search down for the #endif.

#### TODO:
* Allow for match find to search downward for the #endif.