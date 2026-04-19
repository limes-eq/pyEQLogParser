# pyEQLogParser
Browser-based python rewrite of EQLogParser for emu servers

All credit for the logic to the original EQLogParser: https://github.com/kauffman12/EQLogParser

I wanted to fix direct damage breakouts for emu servers, ran into the SyncFusion depdendency in the main branch, and decided to convert into a fresh take on the idea instead

The web UI allows specifying a spells_us.txt to use for DD parsing, you can also replace the default copy in pyEQLogParser/_internal/resources to avoid having to specify a path every run

<img width="1664" height="542" alt="Screenshot 2026-04-18 233550" src="https://github.com/user-attachments/assets/c945d99f-5543-446c-88e3-377d6189d064" />

<img width="1663" height="685" alt="Screenshot 2026-04-18 233721" src="https://github.com/user-attachments/assets/96acdecc-731a-4ceb-a513-b165be7ea741" />

# How to Run

## Download the packaged release and run (Windows)
No additional config needed, replace pyEQLogParser/_internal/resources/spells_us.txt with a copy from your server

## Run via Python (platform independent, requirements.txt included)
`python launch.py` and then launch http://localhost:5000 in a browser

## Create standalone package
`build.bat`
