"""Tests for taskview library — pass 1: derived from SPEC.md before implementation."""
import unittest
import sys
import os
import tempfile
import yaml
from pathlib import Path
from io import StringIO
import contextlib

# Import convention: add repo root to path, then import from tools.taskview.taskview
ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
sys.path.insert(0, ROOT)
from tools.taskview.taskview import (
	load_filter,
	discover_filter,
	resolve_filter,
	select_tasks,
	compute_metrics,
	build_view,
	read_csv,
	FilterError,
	resolve_data_dir,
	resolve_csv,
	watch_targets,
	truncate,
	task_label,
)

# Module-level test isolation: redirect XDG_DATA_HOME to a unique temp directory
# so no test can ever touch the real ~/.local/share/taskview (R17, R19).
_TEST_XDG_DATA_HOME = None
_REAL_XDG_DATA_HOME = None

def setUpModule():
	global _TEST_XDG_DATA_HOME, _REAL_XDG_DATA_HOME
	_REAL_XDG_DATA_HOME = os.environ.get('XDG_DATA_HOME')
	_TEST_XDG_DATA_HOME = tempfile.mkdtemp(prefix='taskview_test_')
	os.environ['XDG_DATA_HOME'] = _TEST_XDG_DATA_HOME

def tearDownModule():
	global _TEST_XDG_DATA_HOME, _REAL_XDG_DATA_HOME
	if _REAL_XDG_DATA_HOME is not None:
		os.environ['XDG_DATA_HOME'] = _REAL_XDG_DATA_HOME
	elif 'XDG_DATA_HOME' in os.environ:
		del os.environ['XDG_DATA_HOME']
	if _TEST_XDG_DATA_HOME and os.path.exists(_TEST_XDG_DATA_HOME):
		import shutil
		shutil.rmtree(_TEST_XDG_DATA_HOME, ignore_errors=True)


class InterfaceTests(unittest.TestCase):
	"""Interfaces section: the names exist and have documented shapes."""

	# Interfaces
	def test_load_filter_exists_and_returns_dict(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
			f.write("label: Test\ncategories: [A]\ntags: [t1]\ninclude_bucket: true\nlimits:\n  upcoming: 3\n  queue_breakdown: false\n")
			path = f.name
		try:
			result = load_filter(path)
			self.assertIsInstance(result, dict)
			self.assertIn('label', result)
			self.assertIn('categories', result)
			self.assertIn('tags', result)
			self.assertIn('include_bucket', result)
			self.assertIn('limits', result)
			self.assertIn('_path', result)
			self.assertIsInstance(result['categories'], set)
			self.assertIsInstance(result['tags'], set)
			self.assertIsInstance(result['limits'], dict)
			self.assertIn('upcoming', result['limits'])
			self.assertIn('queue_breakdown', result['limits'])
		finally:
			os.unlink(path)

	# Interfaces, R8
	def test_load_filter_raises_FilterError_on_malformed_yaml(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
			f.write("label: Test\ncategories: [A\n")  # invalid YAML
			path = f.name
		try:
			with self.assertRaises(FilterError):
				load_filter(path)
		finally:
			os.unlink(path)

	# Interfaces
	def test_discover_filter_exists(self):
		with tempfile.TemporaryDirectory() as tmp:
			result = discover_filter(Path(tmp))
			self.assertIsNone(result)

	# Interfaces, R9a
	def test_resolve_filter_exists(self):
		with tempfile.TemporaryDirectory() as tmp:
			result = resolve_filter(Path(tmp), None, False)
			self.assertIsInstance(result, tuple)
			self.assertEqual(len(result), 3)
			path, filter_data, source = result
			self.assertIsNone(path)
			self.assertIsNone(filter_data)
			self.assertEqual(source, 'none')

	# Interfaces
	def test_select_tasks_exists_and_returns_dict(self):
		state = {1: {'id': 1, 'status': 'open', 'title': 't', 'due_ts': None, 'chg_ts': 0, 'category': '', 'tags': set(), 'importance': ''}}
		result = select_tasks(state, None)
		self.assertIsInstance(result, dict)

	# Interfaces
	def test_compute_metrics_exists_and_returns_dict(self):
		state = {1: {'id': 1, 'status': 'open', 'title': 't', 'due_ts': None, 'chg_ts': 0, 'category': '', 'tags': set(), 'importance': ''}}
		selected = {1: state[1]}
		result = compute_metrics(state, selected, None)
		self.assertIsInstance(result, dict)
		for key in ('done_day', 'done_week', 'done_month', 'active', 'this_week', 'this_month', 'later', 'open_tasks', 'shown', 'filtered_total'):
			self.assertIn(key, result)

	# Interfaces
	def test_build_view_exists_and_returns_str(self):
		selected = {1: {'id': 1, 'status': 'open', 'title': 't', 'due_ts': None, 'chg_ts': 0, 'category': '', 'tags': set(), 'importance': '', 'description': ''}}
		metrics = {'done_day': 0, 'done_week': 0, 'done_month': 0, 'active': 1, 'this_week': 0, 'this_month': 0, 'later': 1, 'open_tasks': list(selected.values()), 'shown': 1, 'filtered_total': 0}
		result = build_view(selected, metrics, None, 80, 24, 'none')
		self.assertIsInstance(result, str)

	# Interfaces
	def test_read_csv_exists_and_returns_dict(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
			f.write("id,status,title,due_ts,chg_ts,category,tags,importance\n1,open,test,,0,,,\n")
			path = f.name
		try:
			result = read_csv(Path(path))
			self.assertIsInstance(result, dict)
		finally:
			os.unlink(path)

	# Interfaces
	def test_FilterError_exists(self):
		self.assertTrue(issubclass(FilterError, Exception))

	# Interfaces, R17
	def test_resolve_data_dir_exists_and_returns_path(self):
		# No explicit, no env vars → uses XDG_DATA_HOME/taskview
		result = resolve_data_dir(None, {})
		self.assertIsInstance(result, Path)
		self.assertEqual(result, Path(_TEST_XDG_DATA_HOME) / 'taskview')

	# R17
	def test_resolve_data_dir_explicit_wins(self):
		with tempfile.TemporaryDirectory() as tmp:
			explicit = Path(tmp) / 'explicit_data'
			result = resolve_data_dir(explicit, {'TASKVIEW_DATA_DIR': '/ignored'})
			self.assertEqual(result, explicit)

	# R17
	def test_resolve_data_dir_taskview_data_dir_env(self):
		with tempfile.TemporaryDirectory() as tmp:
			env_path = Path(tmp) / 'from_env'
			environ = {'TASKVIEW_DATA_DIR': str(env_path)}
			result = resolve_data_dir(None, environ)
			self.assertEqual(result, env_path)

	# Interfaces, R18
	def test_resolve_csv_exists_and_returns_path(self):
		with tempfile.TemporaryDirectory() as tmp:
			data_dir = Path(tmp) / 'data'
			result = resolve_csv(data_dir, None)
			self.assertEqual(result, data_dir / 'tasks.csv')

	# R18
	def test_resolve_csv_explicit_wins(self):
		with tempfile.TemporaryDirectory() as tmp:
			data_dir = Path(tmp) / 'data'
			explicit = Path(tmp) / 'custom.csv'
			result = resolve_csv(data_dir, explicit)
			self.assertEqual(result, explicit)

	# Interfaces, R22
	def test_watch_targets_exists_and_returns_list(self):
		with tempfile.TemporaryDirectory() as tmp:
			csv_path = Path(tmp) / 'tasks.csv'
			result = watch_targets(csv_path, None)
			self.assertIsInstance(result, list)
			self.assertEqual(result, [csv_path])

	# R22
	def test_watch_targets_includes_filter_when_present(self):
		with tempfile.TemporaryDirectory() as tmp:
			csv_path = Path(tmp) / 'tasks.csv'
			filter_path = Path(tmp) / '.taskview.yaml'
			filter_path.write_text("label: Test\n")
			result = watch_targets(csv_path, filter_path)
			self.assertIsInstance(result, list)
			self.assertEqual(set(result), {csv_path, filter_path})

	# R22
	def test_watch_targets_deduplicates_same_path(self):
		with tempfile.TemporaryDirectory() as tmp:
			csv_path = Path(tmp) / 'tasks.csv'
			result = watch_targets(csv_path, csv_path)
			self.assertEqual(result, [csv_path])


class FilterLoadingTests(unittest.TestCase):
	"""R6-R8: filter file keys, defaults, unknown keys, malformed YAML, empty file."""

	# R6
	def test_all_recognised_keys_loaded(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
			f.write("""label: MyProject
categories: [XLib, Agents]
tags: [critical, urgent]
include_bucket: true
limits:
  upcoming: 7
  queue_breakdown: false
""")
			path = f.name
		try:
			result = load_filter(path)
			self.assertEqual(result['label'], 'MyProject')
			self.assertEqual(result['categories'], {'XLib', 'Agents'})
			self.assertEqual(result['tags'], {'critical', 'urgent'})
			self.assertTrue(result['include_bucket'])
			self.assertEqual(result['limits']['upcoming'], 7)
			self.assertFalse(result['limits']['queue_breakdown'])
		finally:
			os.unlink(path)

	# R6
	def test_defaults_for_absent_keys(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
			f.write("label: Minimal\n")
			path = f.name
		try:
			result = load_filter(path)
			self.assertEqual(result['label'], 'Minimal')
			self.assertEqual(result['categories'], set())
			self.assertEqual(result['tags'], set())
			self.assertFalse(result['include_bucket'])
			self.assertEqual(result['limits']['upcoming'], 5)
			self.assertTrue(result['limits']['queue_breakdown'])
		finally:
			os.unlink(path)

	# R7
	def test_unknown_key_warns_on_stderr_and_does_not_raise(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
			f.write("label: Test\ntyop: oops\n")
			path = f.name
		try:
			stderr = StringIO()
			with contextlib.redirect_stderr(stderr):
				result = load_filter(path)
			output = stderr.getvalue()
			self.assertIn('tyop', output)
			self.assertIn('unknown', output.lower())
			self.assertEqual(result['label'], 'Test')
		finally:
			os.unlink(path)

	# R8
	def test_malformed_yaml_raises_FilterError(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
			f.write("label: Test\ncategories: [unclosed\n")
			path = f.name
		try:
			with self.assertRaises(FilterError):
				load_filter(path)
		finally:
			os.unlink(path)

	# R6, R8
	def test_empty_file_returns_defaults(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
			f.write("")
			path = f.name
		try:
			result = load_filter(path)
			self.assertEqual(result['label'], Path(path).stem)
			self.assertEqual(result['categories'], set())
			self.assertEqual(result['tags'], set())
			self.assertFalse(result['include_bucket'])
		finally:
			os.unlink(path)

	# Interfaces
	def test_load_filter_returns_path_in_result(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
			f.write("label: Test\n")
			path = f.name
		try:
			result = load_filter(path)
			self.assertEqual(result['_path'], Path(path))
		finally:
			os.unlink(path)


class SelectionPrecedenceTests(unittest.TestCase):
	"""R14-R16: all five rules and their interactions."""

	def _make_task(self, task_id, category='', tags=None, status='open'):
		if tags is None:
			tags = set()
		return {
			'id': task_id,
			'status': status,
			'title': f'Task {task_id}',
			'due_ts': None,
			'chg_ts': 1000 + task_id,
			'category': category,
			'tags': set(tags),
			'importance': '',
		}

	def _make_filter(self, categories=None, tags=None, include_bucket=False):
		if categories is None:
			categories = []
		if tags is None:
			tags = []
		return {
			'label': 'Test',
			'categories': set(categories),
			'tags': set(tags),
			'include_bucket': include_bucket,
			'limits': {'upcoming': 5, 'queue_breakdown': True},
		}

	# R14 rule 1
	def test_rule1_never_show_cancelled_excluded_unconditionally(self):
		state = {1: self._make_task(1, tags={'cancelled'})}
		filter_data = self._make_filter()
		result = select_tasks(state, filter_data)
		self.assertNotIn(1, result)

	# R14 rule 1
	def test_rule1_never_show_archived_excluded_unconditionally(self):
		state = {1: self._make_task(1, tags={'archived'})}
		filter_data = self._make_filter()
		result = select_tasks(state, filter_data)
		self.assertNotIn(1, result)

	# R14 rule 2
	def test_rule2_category_not_accepted_excluded(self):
		state = {1: self._make_task(1, category='Other')}
		filter_data = self._make_filter(categories=['MyProject'])
		result = select_tasks(state, filter_data)
		self.assertNotIn(1, result)

	# R14 rule 2, R4
	def test_rule2_empty_categories_list_allows_all_categories(self):
		state = {1: self._make_task(1, category='Anything')}
		filter_data = self._make_filter(categories=[])
		result = select_tasks(state, filter_data)
		self.assertIn(1, result)

	# R14 rule 2, R3
	def test_rule2_uncategorised_with_include_bucket_true_included(self):
		state = {1: self._make_task(1, category='')}
		filter_data = self._make_filter(categories=['MyProject'], include_bucket=True)
		result = select_tasks(state, filter_data)
		self.assertIn(1, result)

	# R14 rule 2, R3
	def test_rule2_uncategorised_with_include_bucket_false_excluded(self):
		state = {1: self._make_task(1, category='')}
		filter_data = self._make_filter(categories=['MyProject'], include_bucket=False)
		result = select_tasks(state, filter_data)
		self.assertNotIn(1, result)

	# R14 rule 3
	def test_rule3_critical_included_bypasses_tag_rule(self):
		state = {1: self._make_task(1, category='MyProject', tags={'critical'})}
		filter_data = self._make_filter(categories=['MyProject'], tags=['work'])
		result = select_tasks(state, filter_data)
		self.assertIn(1, result)

	# R14 rule 3
	def test_rule3_emergency_included_bypasses_tag_rule(self):
		state = {1: self._make_task(1, category='MyProject', tags={'emergency'})}
		filter_data = self._make_filter(categories=['MyProject'], tags=['work'])
		result = select_tasks(state, filter_data)
		self.assertIn(1, result)

	# R14 rule 2 precedes rule 3, R15
	def test_rule3_critical_with_nonmatching_category_excluded(self):
		state = {1: self._make_task(1, category='Other', tags={'critical'})}
		filter_data = self._make_filter(categories=['MyProject'])
		result = select_tasks(state, filter_data)
		self.assertNotIn(1, result)

	# R14 rule 4
	def test_rule4_tag_filter_nonempty_no_overlap_excluded(self):
		state = {1: self._make_task(1, category='MyProject', tags={'personal'})}
		filter_data = self._make_filter(categories=['MyProject'], tags=['work'])
		result = select_tasks(state, filter_data)
		self.assertNotIn(1, result)

	# R14 rule 4
	def test_rule4_tag_filter_empty_allows_all_tags(self):
		state = {1: self._make_task(1, category='MyProject', tags={'anything'})}
		filter_data = self._make_filter(categories=['MyProject'], tags=[])
		result = select_tasks(state, filter_data)
		self.assertIn(1, result)

	# R14 rule 5
	def test_rule5_default_included(self):
		state = {1: self._make_task(1, category='MyProject', tags={'work'})}
		filter_data = self._make_filter(categories=['MyProject'], tags=['work'])
		result = select_tasks(state, filter_data)
		self.assertIn(1, result)

	# R14, Interfaces (None filter = all pass except rule 1)
	def test_none_filter_all_passes_except_never_show(self):
		state = {
			1: self._make_task(1, category='Anything', tags={'anything'}),
			2: self._make_task(2, tags={'cancelled'}),
		}
		result = select_tasks(state, None)
		self.assertIn(1, result)
		self.assertNotIn(2, result)

	# R14 rules 2+3 interaction
	def test_critical_in_bucket_with_include_bucket_true_included(self):
		state = {1: self._make_task(1, category='', tags={'critical'})}
		filter_data = self._make_filter(categories=['MyProject'], include_bucket=True)
		result = select_tasks(state, filter_data)
		self.assertIn(1, result)

	# R15: category precedes critical
	def test_critical_in_bucket_with_include_bucket_false_excluded_by_rule2(self):
		state = {1: self._make_task(1, category='', tags={'critical'})}
		filter_data = self._make_filter(categories=['MyProject'], include_bucket=False)
		result = select_tasks(state, filter_data)
		self.assertNotIn(1, result)


class SPlusFInvariantTests(unittest.TestCase):
	"""R25: S + F = open tasks not excluded by rule 1 (never-show)."""

	def _make_task(self, task_id, category='', tags=None, status='open'):
		if tags is None:
			tags = set()
		return {
			'id': task_id,
			'status': status,
			'title': f'Task {task_id}',
			'due_ts': None,
			'chg_ts': 1000 + task_id,
			'category': category,
			'tags': set(tags),
			'importance': '',
		}

	def _make_filter(self, categories=None, tags=None, include_bucket=False):
		if categories is None:
			categories = []
		if tags is None:
			tags = []
		return {
			'label': 'Test',
			'categories': set(categories),
			'tags': set(tags),
			'include_bucket': include_bucket,
			'limits': {'upcoming': 5, 'queue_breakdown': True},
		}

	# R25
	def test_invariant_holds_with_mixed_tasks(self):
		state = {
			1: self._make_task(1, category='MyProject', tags={'work'}),      # included
			2: self._make_task(2, category='Other', tags={'work'}),           # excluded by category
			3: self._make_task(3, category='', tags={'work'}),                # excluded (no bucket)
			4: self._make_task(4, category='', tags={'work'}),                # excluded (no bucket)
			5: self._make_task(5, tags={'cancelled'}),                        # excluded by rule 1
			6: self._make_task(6, category='MyProject', tags={'critical'}),   # included (critical)
			7: self._make_task(7, category='MyProject', tags={'personal'}),   # excluded by tag filter
		}
		filter_data = self._make_filter(categories=['MyProject'], tags=['work'], include_bucket=False)
		selected = select_tasks(state, filter_data)
		metrics = compute_metrics(state, selected, filter_data)
		open_not_rule1 = sum(1 for t in state.values() if t['status'] == 'open' and not (t['tags'] & {'cancelled', 'archived'}))
		self.assertEqual(metrics['shown'] + metrics['filtered_total'], open_not_rule1)

	# R25
	def test_invariant_holds_with_all_uncategorised_and_bucket(self):
		state = {
			1: self._make_task(1, category='', tags={'work'}),
			2: self._make_task(2, category='', tags={'personal'}),
			3: self._make_task(3, tags={'cancelled'}),
		}
		filter_data = self._make_filter(categories=['MyProject'], include_bucket=True)
		selected = select_tasks(state, filter_data)
		metrics = compute_metrics(state, selected, filter_data)
		open_not_rule1 = sum(1 for t in state.values() if t['status'] == 'open' and not (t['tags'] & {'cancelled', 'archived'}))
		self.assertEqual(metrics['shown'] + metrics['filtered_total'], open_not_rule1)

	# R25, R12
	def test_invariant_holds_with_no_filter(self):
		state = {
			1: self._make_task(1, category='A', tags={'x'}),
			2: self._make_task(2, category='B', tags={'y'}),
			3: self._make_task(3, tags={'cancelled'}),
		}
		selected = select_tasks(state, None)
		metrics = compute_metrics(state, selected, None)
		open_not_rule1 = sum(1 for t in state.values() if t['status'] == 'open' and not (t['tags'] & {'cancelled', 'archived'}))
		self.assertEqual(metrics['shown'] + metrics['filtered_total'], open_not_rule1)

	# R16, R25
	def test_invariant_excludes_never_show_from_both_counts(self):
		state = {
			1: self._make_task(1, category='MyProject', tags={'work'}),
			2: self._make_task(2, tags={'cancelled'}),
			3: self._make_task(3, tags={'archived'}),
		}
		filter_data = self._make_filter(categories=['MyProject'], tags=['work'])
		selected = select_tasks(state, filter_data)
		metrics = compute_metrics(state, selected, filter_data)
		open_not_rule1 = sum(1 for t in state.values() if t['status'] == 'open' and not (t['tags'] & {'cancelled', 'archived'}))
		self.assertEqual(metrics['shown'] + metrics['filtered_total'], open_not_rule1)
		self.assertEqual(metrics['shown'], 1)
		self.assertEqual(metrics['filtered_total'], 0)


class DiscoveryTests(unittest.TestCase):
	"""R9-R13: filter discovery and resolution."""

	# R9 rule 1
	def test_explicit_filter_beats_discovery(self):
		with tempfile.TemporaryDirectory() as tmp:
			tmp = Path(tmp)
			# Create a filter in the cwd
			(tmp / '.taskview.yaml').write_text("label: CWD\n")
			# Create a different explicit filter
			explicit = tmp / 'explicit.yaml'
			explicit.write_text("label: Explicit\n")
			path, filter_data, source = resolve_filter(tmp, explicit, False)
			self.assertEqual(path, explicit)
			self.assertEqual(filter_data['label'], 'Explicit')
			self.assertEqual(source, 'explicit')

	# R9 rule 2
	def test_discovery_walks_up_from_cwd(self):
		with tempfile.TemporaryDirectory() as tmp:
			tmp = Path(tmp)
			project = tmp / 'project'
			subdir = project / 'subdir'
			subdir.mkdir(parents=True)
			(project / '.taskview.yaml').write_text("label: Project\n")
			path, filter_data, source = resolve_filter(subdir, None, False)
			self.assertEqual(path, project / '.taskview.yaml')
			self.assertEqual(filter_data['label'], 'Project')
			self.assertEqual(source, 'discovered')

	# R9 rule 2, R11
	def test_nearest_ancestor_wins(self):
		with tempfile.TemporaryDirectory() as tmp:
			tmp = Path(tmp)
			parent = tmp / 'parent'
			child = parent / 'child'
			child.mkdir(parents=True)
			(tmp / '.taskview.yaml').write_text("label: Root\n")
			(parent / '.taskview.yaml').write_text("label: Parent\n")
			path, filter_data, source = resolve_filter(child, None, False)
			self.assertEqual(path, parent / '.taskview.yaml')
			self.assertEqual(filter_data['label'], 'Parent')
			self.assertEqual(source, 'discovered')

	# R10
	def test_symlinked_cwd_resolves_to_real_path(self):
		with tempfile.TemporaryDirectory() as tmp:
			tmp = Path(tmp)
			real_project = tmp / 'real_project'
			real_project.mkdir()
			(real_project / '.taskview.yaml').write_text("label: Real\n")
			symlink = tmp / 'symlink_project'
			symlink.symlink_to(real_project)
			path, filter_data, source = resolve_filter(symlink, None, False)
			self.assertEqual(path, real_project / '.taskview.yaml')
			self.assertEqual(source, 'discovered')

	# R9 rule 3, R12
	def test_nothing_found_returns_none_none(self):
		with tempfile.TemporaryDirectory() as tmp:
			tmp = Path(tmp)
			subdir = tmp / 'subdir'
			subdir.mkdir()
			path, filter_data, source = resolve_filter(subdir, None, False)
			self.assertIsNone(path)
			self.assertIsNone(filter_data)
			self.assertEqual(source, 'none')

	# R13
	def test_no_filter_flag_returns_none_none(self):
		with tempfile.TemporaryDirectory() as tmp:
			tmp = Path(tmp)
			(tmp / '.taskview.yaml').write_text("label: Project\n")
			path, filter_data, source = resolve_filter(tmp, None, True)
			self.assertIsNone(path)
			self.assertIsNone(filter_data)
			self.assertEqual(source, 'flag')

	# R11
	def test_parent_filter_captures_child(self):
		with tempfile.TemporaryDirectory() as tmp:
			tmp = Path(tmp)
			parent = tmp / 'parent'
			child = parent / 'child' / 'grandchild'
			child.mkdir(parents=True)
			(parent / '.taskview.yaml').write_text("label: Parent\n")
			path, filter_data, source = resolve_filter(child, None, False)
			self.assertEqual(path, parent / '.taskview.yaml')
			self.assertEqual(filter_data['label'], 'Parent')
			self.assertEqual(source, 'discovered')

	# R11
	def test_walk_does_not_stop_at_home(self):
		# We can't easily test HOME boundary, but we can verify it walks past a directory named "home"
		with tempfile.TemporaryDirectory() as tmp:
			tmp = Path(tmp)
			fake_home = tmp / 'home' / 'user'
			project = fake_home / 'project'
			project.mkdir(parents=True)
			(tmp / '.taskview.yaml').write_text("label: Root\n")
			path, filter_data, source = resolve_filter(project, None, False)
			self.assertEqual(path, tmp / '.taskview.yaml')
			self.assertEqual(source, 'discovered')

	# R9, R11
	def test_discover_filter_returns_none_when_no_filter(self):
		with tempfile.TemporaryDirectory() as tmp:
			result = discover_filter(Path(tmp))
			self.assertIsNone(result)

	# R9, R11
	def test_discover_filter_finds_first_yaml_upwards(self):
		with tempfile.TemporaryDirectory() as tmp:
			tmp = Path(tmp)
			project = tmp / 'a' / 'b' / 'c'
			project.mkdir(parents=True)
			(tmp / 'a' / '.taskview.yaml').write_text("label: Found\n")
			result = discover_filter(project)
			self.assertEqual(result, tmp / 'a' / '.taskview.yaml')


class HeaderStatesTests(unittest.TestCase):
	"""R24: three exact header strings, mutually distinguishable."""

	def _make_selected(self, count=1):
		return {i: {'id': i, 'status': 'open', 'title': f'Task {i}', 'due_ts': None, 'chg_ts': 1000+i, 'category': '', 'tags': set(), 'importance': '', 'description': ''} for i in range(1, count+1)}

	def _make_metrics(self, shown=1, filtered=0):
		open_tasks = list(self._make_selected(shown).values())
		return {'done_day': 0, 'done_week': 0, 'done_month': 0, 'active': shown, 'this_week': 0, 'this_month': 0, 'later': shown, 'open_tasks': open_tasks, 'shown': shown, 'filtered_total': filtered}

	# R24
	def test_filter_found_header(self):
		filter_data = {'label': 'MyProject', 'categories': set(), 'tags': set(), 'include_bucket': False, 'limits': {'upcoming': 5, 'queue_breakdown': True}}
		selected = self._make_selected()
		metrics = self._make_metrics()
		view = build_view(selected, metrics, filter_data, 80, 24, 'explicit')
		self.assertIn('=== Tasks (MyProject) ===', view)

	# R24, R12
	def test_no_filter_found_header(self):
		filter_data = None
		selected = self._make_selected()
		metrics = self._make_metrics()
		view = build_view(selected, metrics, filter_data, 80, 24, 'none')
		self.assertIn('=== Tasks (no filter found \u2014 showing all) ===', view)

	# R24, R13
	def test_no_filter_flag_header(self):
		# With R9a, resolve_filter returns source='flag' for --no-filter
		# build_view receives filter_data=None and source='flag'
		filter_data = None
		selected = self._make_selected()
		metrics = self._make_metrics()
		view = build_view(selected, metrics, filter_data, 80, 24, 'flag')
		self.assertIn('=== Tasks (no filter) ===', view)

	# R24
	def test_three_headers_are_mutually_distinguishable(self):
		filter_data1 = {'label': 'X', 'categories': set(), 'tags': set(), 'include_bucket': False, 'limits': {'upcoming': 5, 'queue_breakdown': True}}
		selected = self._make_selected()
		metrics = self._make_metrics()
		view1 = build_view(selected, metrics, filter_data1, 80, 24, 'explicit')
		view2 = build_view(selected, metrics, None, 80, 24, 'none')
		view3 = build_view(selected, metrics, None, 80, 24, 'flag')
		self.assertNotEqual(view1.split('\n')[0], view2.split('\n')[0])
		self.assertNotEqual(view2.split('\n')[0], view3.split('\n')[0])
		self.assertNotEqual(view1.split('\n')[0], view3.split('\n')[0])


class PurityTests(unittest.TestCase):
	"""R20, R27: pure functions, deterministic output, --width honoured."""

	def _make_selected(self):
		return {1: {'id': 1, 'status': 'open', 'title': 'Test Task', 'due_ts': None, 'chg_ts': 1000, 'category': 'X', 'tags': set(), 'importance': '', 'description': ''}}

	def _make_metrics(self, selected=None):
		"""Return a metrics dict. If selected is given, populate open_tasks from it."""
		open_tasks = list(selected.values()) if selected else []
		return {'done_day': 0, 'done_week': 0, 'done_month': 0, 'active': len(open_tasks), 'this_week': 0, 'this_month': 0, 'later': len(open_tasks), 'open_tasks': open_tasks, 'shown': len(open_tasks), 'filtered_total': 0}

	# R27
	def test_build_view_deterministic_same_input_same_output(self):
		filter_data = {'label': 'Test', 'categories': {'X'}, 'tags': set(), 'include_bucket': False, 'limits': {'upcoming': 5, 'queue_breakdown': True}}
		selected = self._make_selected()
		metrics = self._make_metrics(selected)
		view1 = build_view(selected, metrics, filter_data, 80, 24, 'explicit')
		view2 = build_view(selected, metrics, filter_data, 80, 24, 'explicit')
		self.assertEqual(view1, view2)

	# R20, R27
	def test_build_view_width_parameter_honoured(self):
		filter_data = {'label': 'Test', 'categories': {'X'}, 'tags': set(), 'include_bucket': False, 'limits': {'upcoming': 5, 'queue_breakdown': True}}
		selected = {1: {'id': 1, 'status': 'open', 'title': 'A' * 100, 'due_ts': None, 'chg_ts': 1000, 'category': 'X', 'tags': set(), 'importance': '', 'description': ''}}
		metrics = self._make_metrics(selected)
		view_narrow = build_view(selected, metrics, filter_data, 20, 24, 'explicit')
		view_wide = build_view(selected, metrics, filter_data, 200, 24, 'explicit')
		# Narrow should truncate, wide should not
		self.assertIn('...', view_narrow)
		self.assertNotIn('...', view_wide)

	# R21, R27
	def test_select_tasks_pure(self):
		state = {1: {'id': 1, 'status': 'open', 'title': 't', 'due_ts': None, 'chg_ts': 0, 'category': 'A', 'tags': set(), 'importance': ''}}
		filter_data = {'label': 'T', 'categories': {'A'}, 'tags': set(), 'include_bucket': False, 'limits': {'upcoming': 5, 'queue_breakdown': True}}
		result1 = select_tasks(state, filter_data)
		result2 = select_tasks(state, filter_data)
		self.assertEqual(result1, result2)

	# R21, R27
	def test_compute_metrics_pure(self):
		state = {1: {'id': 1, 'status': 'open', 'title': 't', 'due_ts': None, 'chg_ts': 0, 'category': 'A', 'tags': set(), 'importance': ''}}
		selected = {1: state[1]}
		filter_data = {'label': 'T', 'categories': {'A'}, 'tags': set(), 'include_bucket': False, 'limits': {'upcoming': 5, 'queue_breakdown': True}}
		result1 = compute_metrics(state, selected, filter_data)
		result2 = compute_metrics(state, selected, filter_data)
		self.assertEqual(result1, result2)


class TaskIdDisplayTests(unittest.TestCase):
	"""R42: the pane shows the task id, and the title is not shortened by it."""

	def _task(self, task_id, title, due_ts=None):
		return {'id': task_id, 'status': 'open', 'title': title, 'due_ts': due_ts,
				'chg_ts': 1000, 'category': 'X', 'tags': set(), 'importance': '', 'description': ''}

	def _view(self, tasks, width):
		selected = {t['id']: t for t in tasks}
		metrics = {'done_day': 0, 'done_week': 0, 'done_month': 0, 'active': len(tasks),
				   'this_week': 0, 'this_month': 0, 'later': len(tasks),
				   'open_tasks': list(tasks), 'shown': len(tasks), 'filtered_total': 0}
		filter_data = {'label': 'T', 'categories': set(), 'tags': set(),
					   'include_bucket': True,
					   'limits': {'upcoming': 5, 'queue_breakdown': True}}
		return build_view(selected, metrics, filter_data, width, 24, 'explicit')

	def _lines(self, view):
		return [l for l in view.splitlines() if l.startswith('▸') or l.startswith(' ·')]

	# The methods below cover R42 (id shown on both task lines), R43 (prefix
	# comes out of the title's budget), R44 (truncate never exceeds width),
	# R45 (id kept when the budget is too small for a title), and R46 (no task
	# line overflows at any width).

	def test_current_task_line_shows_the_id(self):
		view = self._view([self._task(42, 'part switching')], 80)
		self.assertTrue(any(l.startswith('▸ #42 ') for l in self._lines(view)),
			f"current line must show #42: {self._lines(view)}")

	def test_upcoming_lines_show_the_id(self):
		# With 4 tasks, 2 go to detail, 2 to upcoming
		tasks = [self._task(1, 'first'), self._task(42, 'second'), self._task(7, 'third'), self._task(99, 'fourth')]
		view = self._view(tasks, 80)
		upcoming = [l for l in self._lines(view) if l.startswith(' ·')]
		self.assertEqual(len(upcoming), 2)
		for expected in ('#7', '#99'):
			self.assertTrue(any(expected in l for l in upcoming),
				f"upcoming must show {expected}: {upcoming}")

	def test_task_label_keeps_the_whole_title_when_it_fits(self):
		label = task_label(self._task(42, 'short'), 40)
		self.assertEqual(label, '#42 short')

	def test_task_label_preserves_title_budget(self):
		"""Adding the id must not shorten the title. The title gets budget minus
		the prefix width, so the total is the same as the bare title's budget."""
		budget = 40
		task = self._task(1234, 'A' * 100)
		label = task_label(task, budget)
		self.assertTrue(label.startswith('#1234 '))
		title_part = label[len('#1234 '):]
		# The title gets budget minus the prefix width, under the same rule the
		# bare title would get (truncate reserves 3 for the ellipsis).
		self.assertEqual(title_part, truncate('A' * 100, budget - len('#1234 ')))
		self.assertEqual(len(title_part), budget - len('#1234 '))

	def test_truncate_never_exceeds_width(self):
		for width in range(-2, 20):
			out = truncate('x' * 50, width)
			self.assertLessEqual(len(out), max(0, width),
				f"truncate(x*50, {width}) returned {len(out)} chars: {out!r}")

	def test_lines_fit_narrow_widths(self):
		"""Narrow widths degrade sanely — the id survives, the line does not overflow."""
		tasks = [self._task(1234, 'A title long enough to truncate at narrow widths'),
				 self._task(2, 'another task so UPCOMING has a row too')]
		for width in (60, 30, 20, 14, 10, 8, 6, 4, 2, 1, 0):
			for line in self._lines(self._view(tasks, width)):
				lead = len(line) - len(line.lstrip("▸ ·"))
				body = line[lead:]
				self.assertLessEqual(len(body), max(0, width - lead),
					f"width={width} body overflowed: {line!r}")

	def test_id_survives_when_the_budget_is_tiny(self):
		label = task_label(self._task(1234, 'a title'), 3)
		self.assertTrue(label.startswith('#'), f"the id is the reference, keep it: {label!r}")
		self.assertLessEqual(len(label), 3)

	def test_ellipsis_marks_the_cut_in_both_detail_lines(self):
		# With 2 detail tasks, both detail lines should show ellipsis when truncated
		tasks = [self._task(1, 'A' * 100), self._task(2, 'B' * 100), self._task(3, 'C' * 100)]
		view = self._view(tasks, 30)
		# Find detail lines (start with ▸)
		detail_lines = [l for l in view.splitlines() if l.startswith('▸')]
		self.assertEqual(len(detail_lines), 2, f"expected 2 detail lines: {detail_lines}")
		self.assertTrue(all('...' in l for l in detail_lines), f"expected marked cut in both detail lines: {detail_lines}")


class CSVToleranceTests(unittest.TestCase):
	"""R33, R34: legacy rows, missing columns, bad id/chg_ts, comments, header, last-row-wins."""

	# R33
	def test_5_column_legacy_row_reads_as_uncategorised(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
			f.write("id,status,title,due_ts,chg_ts\n1,open,Legacy Task,,1000\n")
			path = f.name
		try:
			result = read_csv(Path(path))
			self.assertIn(1, result)
			self.assertEqual(result[1]['category'], '')
			self.assertEqual(result[1]['tags'], set())
		finally:
			os.unlink(path)

	# R33
	def test_8_column_row_reads_all_fields(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
			# tags column contains "tag1,tag2" as a single comma-separated field
			f.write('id,status,title,due_ts,chg_ts,category,tags,importance\n1,open,Full Task,,1000,MyProject,"tag1,tag2",high\n')
			path = f.name
		try:
			result = read_csv(Path(path))
			self.assertIn(1, result)
			self.assertEqual(result[1]['category'], 'MyProject')
			self.assertEqual(result[1]['tags'], {'tag1', 'tag2'})
			self.assertEqual(result[1]['importance'], 'high')
		finally:
			os.unlink(path)

	# R34
	def test_non_integer_id_skipped(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
			f.write("id,status,title,due_ts,chg_ts\nnotanint,open,Bad,,1000\n2,open,Good,,2000\n")
			path = f.name
		try:
			result = read_csv(Path(path))
			self.assertNotIn('notanint', result)
			self.assertIn(2, result)
		finally:
			os.unlink(path)

	# R34
	def test_empty_chg_ts_skipped(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
			f.write("id,status,title,due_ts,chg_ts\n1,open,NoChange,,,\n2,open,HasChange,,2000\n")
			path = f.name
		try:
			result = read_csv(Path(path))
			self.assertNotIn(1, result)
			self.assertIn(2, result)
		finally:
			os.unlink(path)

	# R34
	def test_unparseable_chg_ts_skipped(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
			f.write("id,status,title,due_ts,chg_ts\n1,open,BadChange,,abc\n2,open,GoodChange,,2000\n")
			path = f.name
		try:
			result = read_csv(Path(path))
			self.assertNotIn(1, result)
			self.assertIn(2, result)
		finally:
			os.unlink(path)

	# R34
	def test_comment_line_skipped(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
			f.write("id,status,title,due_ts,chg_ts\n// This is a comment\n1,open,Real,,1000\n")
			path = f.name
		try:
			result = read_csv(Path(path))
			self.assertIn(1, result)
			self.assertEqual(len(result), 1)
		finally:
			os.unlink(path)

	# R34
	def test_header_row_skipped(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
			f.write("id,status,title,due_ts,chg_ts,category,tags,importance\n1,open,Real,,1000,,,\n")
			path = f.name
		try:
			result = read_csv(Path(path))
			self.assertIn(1, result)
			self.assertEqual(len(result), 1)
		finally:
			os.unlink(path)

	# R34
	def test_last_row_wins_for_same_id(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
			f.write("id,status,title,due_ts,chg_ts\n1,open,First,,1000\n1,open,Second,,2000\n")
			path = f.name
		try:
			result = read_csv(Path(path))
			self.assertEqual(result[1]['title'], 'Second')
			self.assertEqual(result[1]['chg_ts'], 2000)
		finally:
			os.unlink(path)

	# R34
	def test_last_row_wins_across_status_changes(self):
		with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
			f.write("id,status,title,due_ts,chg_ts\n1,open,Task,,1000\n1,done,Task,,2000\n")
			path = f.name
		try:
			result = read_csv(Path(path))
			self.assertEqual(result[1]['status'], 'done')
		finally:
			os.unlink(path)


class TestIsolationGuard(unittest.TestCase):
	"""R17, R19: Verify the test suite cannot touch the real data directory."""

	# R17, R19
	def test_resolve_data_dir_default_is_in_temp_tree(self):
		# The module-level setUpModule sets XDG_DATA_HOME to a unique temp dir
		# resolve_data_dir with no args should resolve to that temp tree
		data_dir = resolve_data_dir(None, {})
		self.assertTrue(str(data_dir).startswith(_TEST_XDG_DATA_HOME),
			f"Default data dir {data_dir} must be inside test temp tree {_TEST_XDG_DATA_HOME}")

	# R17, R19
	def test_real_data_dir_untouched_by_resolve(self):
		# The real ~/.local/share/taskview must not be created or modified by tests
		# We only assert on our temp tree's contents — never read the real path
		real_default = Path.home() / '.local' / 'share' / 'taskview'
		# If it exists from before, that's the human's data — we must not touch it
		# Our temp tree is separate; this test just documents the invariant
		data_dir = resolve_data_dir(None, {})
		self.assertNotEqual(data_dir, real_default)
		self.assertTrue(str(data_dir).startswith(_TEST_XDG_DATA_HOME))


if __name__ == '__main__':
	unittest.main()