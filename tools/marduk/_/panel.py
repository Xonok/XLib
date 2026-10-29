"""The panel: configuration, state, scheduler and the two run modes."""

import contextlib,shutil,signal,sys,termios,threading,time
from . import config,render,scheduler,store
from .sources import SOURCES

_ENTER_WATCH="\033[?25l\033[?1049h"
_LEAVE_WATCH="\033[?25h\033[?1049l"

@contextlib.contextmanager
def _fullscreen():
	"""Watch mode owns the pane: no cursor, no scrollback, no echo."""
	fd=None
	old_attrs=None
	if sys.stdin.isatty():
		try:
			fd=sys.stdin.fileno()
			old_attrs=termios.tcgetattr(fd)
			new_attrs=termios.tcgetattr(fd)
			new_attrs[3]&=~(termios.ECHO|getattr(termios,"ECHOCTL",0))
			termios.tcsetattr(fd,termios.TCSANOW,new_attrs)
		except (termios.error,OSError,AttributeError):
			fd=None
			old_attrs=None
	sys.stdout.write(_ENTER_WATCH)
	sys.stdout.flush()
	try:
		yield
	finally:
		if old_attrs is not None and fd is not None:
			try:
				termios.tcsetattr(fd,termios.TCSANOW,old_attrs)
			except (termios.error,OSError):
				pass
		sys.stdout.write(_LEAVE_WATCH)
		sys.stdout.flush()

class Panel:
	"""One Marduk panel."""

	def __init__(self,config_path=None,state_path=None,compact:bool=False,poll_seconds:float=1.0,clock=time.time):
		self.config=config.Config(config_path)
		self.store=store.Store(str(state_path or self.config.state_path))
		self.store.load()
		self.store.retention_seconds=self.config.news_retention_days*86400
		self.compact=compact
		self.poll_seconds=poll_seconds
		self.clock=clock
		self.sources=list(SOURCES) if not self.config.error else []
		self.scheduler=scheduler.Scheduler(self.store,self.config,self.sources,clock)

	def render_lines(self,height:int|None=None,width:int|None=None)->list[str]:
		if height is None or width is None:
			size=shutil.get_terminal_size((80,24))
			height=size.lines if height is None else height
			width=size.columns if width is None else width
		now=self.clock()
		notices=[notice for notice in (self.config.error,self.store.load_error) if notice]
		return render.render(self.config,self.sources,self.store.snapshot(now),now,height,width,self.compact,notices)

	def run_once(self)->None:
		self.scheduler.run_due(self.clock(),force=True)
		lines=self.render_lines()
		sys.stdout.write("\n".join(lines)+"\n")
		sys.stdout.flush()

	def run_watch(self)->None:
		stop=threading.Event()
		def handler(signum,frame):
			stop.set()
		signal.signal(signal.SIGTERM,handler)
		signal.signal(signal.SIGINT,handler)
		thread=threading.Thread(target=self.scheduler.run_forever,daemon=True)
		thread.start()
		try:
			with _fullscreen():
				while not stop.is_set():
					lines=self.render_lines()
					text="\n".join(lines)
					if len(lines)<shutil.get_terminal_size((80,24)).lines:
						text+="\n"
					sys.stdout.write("\033[H\033[2J"+text)
					sys.stdout.flush()
					stop.wait(self.poll_seconds)
		finally:
			self.scheduler.stop()
			thread.join(timeout=2.0)
			self.store.save()
