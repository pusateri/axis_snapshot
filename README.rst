=============
axis_snapshot
=============


Grab a still snapshot from an AXIS network camera.


Description
===========

This command will grab a still snapshot from a network camera. It is meant
to be run from cron.

Snapshots are only taken between sunrise and sunset.

Login credentials MUST be stored in a .netrc file.

Note
====

Command can be invoked as:

# snapshot -n <name (no spaces)> -l <lat> -g <long> https://camera.example.com/jpg/image.jpg


Testing your camera with curl can be done with:

curl -o sample.jpg --digest --netrc-file ~/.netrc https://camera.example.com/jpg/image.jpg


