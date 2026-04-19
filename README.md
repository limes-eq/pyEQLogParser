# pyEQLogParser
Browser-based python rewrite of EQLogParser for emu servers

All credit for the logic to the original EQLogParser: https://github.com/kauffman12/EQLogParser

I wanted to fix direct damage breakouts for emu servers, ran into the SyncFusion depdendency in the main branch, and decided to convert into a fresh take on the idea instead

The web UI allows specifying a spells_us.txt to use for DD parsing, you can also replace the default copy in pyEQLogParser/_internal/resources to avoid having to specify a path every run

<img width="1698" height="556" alt="image" src="https://github.com/user-attachments/assets/d7981a66-029e-480e-8f02-3e8978d14ade" />

<img width="1693" height="729" alt="image" src="https://github.com/user-attachments/assets/6ba1d10b-168b-4bb3-a8e8-3752a903694b" />

# How to Run

## Download the packaged release and run (Windows)
No additional config needed, replace pyEQLogParser/_internal/resources/spells_us.txt with a copy from your server

## Run via Python (platform independent, requirements.txt included)
`python launch.py` and then launch http://localhost:5000 in a browser

## Create standalone package
`build.bat`
