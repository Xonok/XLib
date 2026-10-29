#!/usr/bin/env python3
"""Marduk - a rare-events panel: a fixed health list and filtered news.

Terminal contract: TERMINAL.md.
"""

import argparse,sys
from pathlib import Path
from ._ import panel

def main(argv:list[str]|None=None)->int:
	parser=argparse.ArgumentParser(description="Marduk - a rare-events panel")
	parser.add_argument("--watch",action="store_true",default=True,help="Watch mode (default)")
	parser.add_argument("--once",action="store_true",help="One-shot mode")
	parser.add_argument("--config",type=Path,default=None,help="Config file")
	parser.add_argument("--state",type=Path,default=None,help="State file")
	parser.add_argument("--poll-seconds",type=float,default=1.0,help="Redraw interval")
	parser.add_argument("--compact",action="store_true",help="Compact mode")
	args=parser.parse_args(argv)
	app=panel.Panel(config_path=args.config,state_path=args.state,compact=args.compact,poll_seconds=args.poll_seconds)
	if args.once:
		app.run_once()
	else:
		app.run_watch()
	return 0

if __name__=="__main__":
	sys.exit(main())
