import os
import zipfile
from io import StringIO, FileIO
from pathlib import Path
from unittest import mock

from nose.tools import assert_true, assert_false, assert_equal  # type: ignore
from requests.exceptions import HTTPError

import wpanalyser.analyser as wpa


def p(path_str: str) -> str:
	return str(Path(path_str))


"""
Tests should be run from top level project folder using 'nosetests'
"""
def test_file_open():
	m = mock.mock_open()
	with mock.patch('wpanalyser.analyser.open', m, create=True):
		wpa.open_file('foo', 'r')
		m.assert_called_with('foo', 'r', encoding=None)

	m.side_effect = IOError
	with mock.patch('wpanalyser.analyser.open', m, create=True):
		res = wpa.open_file('foo', 'r')
		m.assert_called_with('foo', 'r', encoding=None)
		assert_false(res)



@mock.patch('wpanalyser.analyser.zipfile.ZipFile')
@mock.patch('wpanalyser.analyser.open_file')
def test_unzip(mock_open_file, mock_zip):
	fakeFile = mock.MagicMock()
	mock_open_file.return_value = fakeFile
	fakeZip = mock.MagicMock()
	fakeZip.namelist.return_value = ['dir/', 'dir/file.txt']
	mock_zip.return_value = fakeZip
	res = wpa.unzip('zipFile.zip', '/')
	mock_open_file.assert_called_with('zipFile.zip', 'rb')
	mock_zip.assert_called_with(fakeFile)
	fakeZip.namelist.assert_called_with()
	calls = [mock.call('dir/','/'), mock.call('dir/file.txt', '/')]
	fakeZip.extract.assert_has_calls(calls)
	assert_equal(res, 'dir/')

	mock_zip.side_effect = RuntimeError
	res = wpa.unzip('zipFile.zip', '/')
	assert_false(res)

	mock_zip.side_effect = IOError
	res = wpa.unzip('zipFile.zip', '/')
	assert_false(res)

	mock_zip.side_effect = zipfile.BadZipfile
	res = wpa.unzip('zipFile.zip', '/')
	assert_false(res)


@mock.patch('wpanalyser.analyser.os.path.isfile')
@mock.patch('wpanalyser.analyser.open_file')
@mock.patch('wpanalyser.analyser.requests')
def test_download_file(mock_requests, mock_open_file, mock_isfile):
	mockFile = mock.MagicMock(spec=FileIO)
	mock_open_file.return_value = mockFile
	mock_isfile.return_value = False
	response = mock.MagicMock()
	mock_requests.get.return_value = response
	response.status_code.return_value = '200'
	response.headers.get.return_value = 2048
	response.iter_content = mock.Mock(return_value=iter(['abc', 'def']))
	wpa.verbose = True
	wpa.download_file("http://file.com/file.txt", ".", "notafile.txt")
	f = os.path.join('.', 'notafile.txt')
	mock_isfile.assert_called_with(f)
	mock_open_file.assert_called_with(f, "wb")
	mock_requests.get.assert_called_with('http://file.com/file.txt', stream=True)
	calls = [mock.call('abc'), mock.call('def')]
	mockFile.write.assert_has_calls(calls)

	wpa.verbose = False
	response.content = 'abcdef'
	wpa.download_file("http://file.com/file.txt", ".", "notafile.txt")
	mockFile.write.assert_called_with('abcdef')

	mock_requests.reset_mock()
	mock_isfile.return_value = True
	res = wpa.download_file("http://file.com", ".", "alreadyafile.txt")
	assert_false(mock_requests.get.called, "Failed to not start download")
	assert_true(res)

	mock_isfile.return_value = False
	mock_open_file.return_value = False
	res = wpa.download_file("http://file.com", ".", "cannotcreatefile.txt")
	assert_false(res)

	response.raise_for_status.side_effect = HTTPError
	res = wpa.download_file("http://file.com", ".", "file.txt")
	response.raise_for_status.assert_called_with()
	assert_false(res)


@mock.patch('wpanalyser.analyser.os.walk')
def test_search_dir_for_exts(mock_walk):
	mock_walk.return_value = []
	res = wpa.search_dir_for_exts('not a dir', ('.txt',))
	mock_walk.assert_called_with('not a dir')
	resCmp: set[str] = set()
	assert_equal(res, resCmp)
	
	mock_walk.return_value = [
		(p('/foo'), ('bar',), ('test.txt', 'temp.doc', 'abc.pdf', 'file.docx')),
		(p('/foo/bar'), (), ('test2.txt', 'abc.pdf')),
	]
	res = wpa.search_dir_for_exts('/foo', ('.txt', '.pdf'))
	s = {p('/foo/test.txt'), p('/foo/abc.pdf'), p('/foo/bar/test2.txt'), p('/foo/bar/abc.pdf')}
	assert_equal(len(res), 4, "Returned set is the wrong size")
	assert_equal(res, s, "Wrong files are returned")


@mock.patch('wpanalyser.analyser.os.path.abspath')
def test_is_subdir(mock_abspath):
	mock_abspath.side_effect = [p('/abs/path/sub/file.txt'), p('/abs/path')]
	res = wpa.is_subdir(p('path/sub/file.txt'), p('path'))
	assert_true(res)

	mock_abspath.side_effect = [p('/abs/path/sub/file.txt'), p('abs/not/same/path')]
	res = wpa.is_subdir(p('path/sub/file.txt'), p('not/same/path'))
	assert_false(res)


@mock.patch('wpanalyser.analyser.is_subdir')
def test_ignored_file(mock_issubdir):
	mock_issubdir.return_value = False
	res = wpa.ignored_file('test/test.php', '/wp')
	mock_issubdir.assert_not_called()
	assert_false(res)

	mock_issubdir.return_value = True
	res = wpa.ignored_file('wp-content/themes/test/index.php', '/wp')
	mock_issubdir.assert_called_with('wp-content/themes/test/index.php', os.path.join('/wp', 'wp-content/themes'))
	assert_true(res)


@mock.patch('wpanalyser.analyser.open_file')
def test_search_file_for_str(mock_open_file):
	mock_open_file.return_value = False
	line = wpa.search_file_for_string('notafile.txt', 'ab')
	assert_false(line)

	mockFile = mock.MagicMock(spec=FileIO)
	mock_open_file.return_value = mockFile
	mockFile.__iter__ = mock.MagicMock(return_value=iter(['abc\n', 'def\n', 'ghi\n']))	
	line = wpa.search_file_for_string('file.txt', 'ab')
	mock_open_file.assert_called_with('file.txt', 'r', encoding='UTF-8')
	assert_equal(line, 'abc\n')

	line = wpa.search_file_for_string('file.txt', 'xyz')
	mock_open_file.assert_called_with('file.txt', 'r', encoding='UTF-8')
	assert_false(line)


@mock.patch('wpanalyser.analyser.search_file_for_string')
def test_find_plugin_details(mock_search_file):
	mock_search_file.return_value = "Stable tag: 1.2.3\n"
	name, version = wpa.find_plugin_details('wp/wp-content/plugins/plugin1/readme.txt')
	mock_search_file.assert_called_with('wp/wp-content/plugins/plugin1/readme.txt', "Stable tag:")
	assert_equal(name, 'plugin1')
	assert_equal(version, '1.2.3')


@mock.patch('wpanalyser.analyser.search_file_for_string')
def test_find_wp_version(mock_search_file):
	mock_search_file.return_value = False
	res = wpa.find_wp_version('file.php')
	mock_search_file.assert_called_with('file.php', '$wp_version =')
	assert_false(res)

	mock_search_file.return_value = "$wp_version = \n"
	res = wpa.find_wp_version('file.php')
	mock_search_file.assert_called_with('file.php', '$wp_version =')
	assert_false(res)

	mock_search_file.return_value = "$wp_version = '1.2.3'\n"
	res = wpa.find_wp_version('file.php')
	mock_search_file.assert_called_with('file.php', '$wp_version =')
	assert_equal(res, '1.2.3')


@mock.patch('wpanalyser.analyser.search_file_for_string')
def test_find_theme_details(mock_search_file):
	mock_search_file.side_effect = ['Text Domain: themename\n', 'Version: 1.2.3\n']
	name, version = wpa.find_theme_details('stylesheet.css')
	calls = [
		mock.call('stylesheet.css', 'Text Domain:'), 
		mock.call('stylesheet.css', 'Version:')]
	mock_search_file.assert_has_calls(calls)
	assert_equal(name, 'themename')
	assert_equal(version, '1.2.3')


@mock.patch('wpanalyser.analyser.download_file')
def test_download_wordpress(mock_download_file):
	mock_download_file.return_value = True
	res, fileName = wpa.download_wordpress('1.4.3', p('tmp'))
	mock_download_file.assert_called_with(wpa.WP_PACKAGE_ARCHIVE_LINK + '1.4.3.zip', 
										  p('tmp'), 'wordpress_1.4.3.zip')
	assert_true(res)
	assert_equal(fileName, p('tmp/wordpress_1.4.3.zip'))

@mock.patch('wpanalyser.analyser.download_file')
@mock.patch('wpanalyser.analyser.unzip')
@mock.patch('wpanalyser.analyser.os.remove')
def test_get_zipped_asset(mock_remove, mock_unzip, mock_download_file):
	mock_download_file.return_value = False
	res = wpa.get_zipped_asset('https://downloads.wordpress.org/thing/thing.1.2.3.zip', 'thing.1.2.3.zip', 'wp')
	mock_download_file.assert_called_with(
					'https://downloads.wordpress.org/thing/thing.1.2.3.zip',
					wpa.TEMP_DIR,
					'thing.1.2.3.zip')
	assert_false(res)

	mock_download_file.return_value = True
	mock_unzip.return_value = 'wp'
	res = wpa.get_zipped_asset('https://downloads.wordpress.org/thing/thing.1.2.3.zip', 'thing.1.2.3.zip', 'wp')
	mock_download_file.assert_called_with(
					'https://downloads.wordpress.org/thing/thing.1.2.3.zip',
					wpa.TEMP_DIR,
					'thing.1.2.3.zip')
	mock_unzip.assert_called_with(os.path.join(wpa.TEMP_DIR, 'thing.1.2.3.zip'), 'wp')
	mock_remove.assert_not_called()
	assert_equal(res, 'wp')	


@mock.patch('wpanalyser.analyser.get_zipped_asset')
@mock.patch('wpanalyser.analyser.os.path.join')
def test_get_plugin(mock_join, mock_get_zipped_asset):
	mock_get_zipped_asset.return_value = 'wp/wp-content/plugins/plugin1'
	mock_join.return_value = 'wp/wp-content/plugins'
	res = wpa.get_plugin('plugin1', '1.2.3', 'wp')
	mock_join.assert_called_with('wp', 'wp-content', 'plugins')
	assert_equal(res, 'wp/wp-content/plugins/plugin1')


@mock.patch('wpanalyser.analyser.get_zipped_asset')
@mock.patch('wpanalyser.analyser.os.path.join')
def test_get_theme(mock_join, mock_get_zipped_asset):
	mock_get_zipped_asset.return_value = 'wp/wp-content/themes/theme1'
	mock_join.return_value = 'wp/wp-content/themes'
	res = wpa.get_theme('plugin1', '1.2.3', 'wp')
	mock_join.assert_called_with('wp', 'wp-content', 'themes')
	assert_equal(res, 'wp/wp-content/themes/theme1')


@mock.patch('wpanalyser.analyser.os.path.isfile')
def test_is_wordpress(mock_isfile):
	mock_isfile.side_effect = [True, True, True, False]
	res = wpa.is_wordpress('/test')
	assert_false(res)

	mock_isfile.side_effect = [True, True, True, True]
	res = wpa.is_wordpress('/test')
	assert_true(res)


@mock.patch('wpanalyser.analyser.os.walk')
@mock.patch('wpanalyser.analyser.os.path.isfile')
def test_get_file_from_from_each_subdirectory(mock_isfile, mock_walk):
	mock_walk.return_value = iter([
			(p('plugins'), ('plugin1', 'plugin2', 'plugin3'), ('readme.txt', 'readme.txt', 'file.txt')),
			(p('plugins/plugin1'), (), ('readme.txt',)),
			(p('plugins/plugin2'), (), ('readme.txt',)),
			(p('plugins/plugin3'), (), ('file.txt',))
		])
	mock_isfile.side_effect = [True, True, False]
	found = list(wpa.get_file_from_each_subdirectory('plugins', 'readme.txt'))
	calls = [
		mock.call(p('plugins/plugin1/readme.txt')),
		mock.call(p('plugins/plugin2/readme.txt')),
		mock.call(p('plugins/plugin3/readme.txt'))
	]
	mock_isfile.assert_has_calls(calls)
	assert_equal(found, [
		p('plugins/plugin1/readme.txt'),
		p('plugins/plugin2/readme.txt')
	])

@mock.patch('wpanalyser.analyser.find_plugin_details')
@mock.patch('wpanalyser.analyser.get_file_from_each_subdirectory')
def test_find_plugins(mock_get_file_from_each, mock_find_plugin_details):
	mock_get_file_from_each.return_value = [p('wp/wp-content/plugins/plugin1/readme.txt'), p('wp/wp-content/plugins/plugin2/readme.txt')]
	mock_find_plugin_details.side_effect = [['plugin1', '1.2.3'], ['plugin2', '1.0']]
	found = list(wpa.find_plugins('wp'))
	mock_get_file_from_each.assert_called_with(p('wp/wp-content/plugins'), 'readme.txt')
	calls = [
		mock.call(p('wp/wp-content/plugins/plugin1/readme.txt')),
		mock.call(p('wp/wp-content/plugins/plugin2/readme.txt'))
	]
	mock_find_plugin_details.assert_has_calls(calls)
	assert_equal(found, [
		('plugin1', '1.2.3'),
		('plugin2', '1.0'),
	])

@mock.patch('wpanalyser.analyser.find_theme_details')
@mock.patch('wpanalyser.analyser.get_file_from_each_subdirectory')
def test_find_themes(mock_get_file_from_each, mock_find_theme_details):
	mock_get_file_from_each.return_value = [p('wp/wp-content/themes/theme1/stylesheet.css'), p('wp/wp-content/themes/theme2/stylesheet.css')]
	mock_find_theme_details.side_effect = [['theme1', '1.2.3'], ['theme2', '1.0']]
	found = list(wpa.find_themes('wp'))
	mock_get_file_from_each.assert_called_with(p('wp/wp-content/themes'), 'style.css')
	calls = [
		mock.call(p('wp/wp-content/themes/theme1/stylesheet.css')),
		mock.call(p('wp/wp-content/themes/theme2/stylesheet.css'))
	]
	mock_find_theme_details.assert_has_calls(calls)
	assert_equal(found, [
		('theme1', '1.2.3'),
		('theme2', '1.0'),
	])


@mock.patch('wpanalyser.analyser.ignored_file')
@mock.patch('wpanalyser.analyser.os.path.isdir')
def test_analyze(mock_isdir, mock_ignored_file):
	mock_isdir.return_value = False
	firstDcRes = mock.MagicMock()
	firstDcRes.left = p('some/path')
	firstDcRes.right = p('other/path')
	firstDcRes.diff_files = ['changed1.txt', 'changed2.txt']
	firstDcRes.left_only = ['extra1.txt', 'extra2.txt']
	firstDcRes.right_only = ['missing1.txt']
	secondDcRes = mock.MagicMock()
	secondDcRes.left = p('some/path/sub')
	secondDcRes.diff_files = ['changed3.txt']
	secondDcRes.left_only = ['extra3.txt']
	firstDcRes.subdirs.values.return_value = [secondDcRes]
	secondDcRes.subdirs.values.return_value = []
	mock_ignored_file.side_effect = [False, False, True] # ignore files in the /sub directory
	diff, extra, missing = wpa.analyze(firstDcRes, 'wp')
	diffCmp =  {p('some/path/changed1.txt'), p('some/path/changed2.txt'), p('some/path/sub/changed3.txt')}
	extraCmp = {p('some/path/extra1.txt'), p('some/path/extra2.txt')}
	missingCmp = {p('other/path/missing1.txt')}
	assert_equal(diff, diffCmp)
	assert_equal(extra, extraCmp)
	assert_equal(missing, missingCmp)


@mock.patch('wpanalyser.analyser.sys.stdout', new_callable=StringIO)
def test_print_analysis(mock_stdout):
	diff = {'diff1.txt', 'diff2.txt'}
	extra = {'extra1.txt', 'extra2.txt'}
	missing = {'missing1.txt', 'missing2.txt'}
	extraPhp = {'extra1.php', 'extra2.php'}
	wpa.print_analysis(diff,extra,missing,extraPhp)
	text = mock_stdout.getvalue()
	assert text == """DIFF: (2)
diff1.txt
diff2.txt
EXTRA: (2)
extra1.txt
extra2.txt
MISSING: (2)
missing1.txt
missing2.txt
PHP FILES IN 'WP-CONTENT/UPLOADS': (2)
extra1.php
extra2.php
"""

@mock.patch('wpanalyser.analyser.argparse.ArgumentParser')
def test_create_args(mock_argparser):
	parser = mock.MagicMock()
	group = mock.MagicMock()
	mock_argparser.return_value = parser
	parser.add_mutually_exclusive_group.return_value = group
	res = wpa.create_args()
	parserCalls = [
		mock.call('wordpress_path', help=mock.ANY),
		mock.call('-t', '--tidy-up', dest='remove_temporary_files', action='store_true', help=mock.ANY),
		mock.call('-v', '--verbose', dest='verbose', action='store_true', help=mock.ANY)
	]
	groupCalls = [
		mock.call('-w', '--with-version', help=mock.ANY),
		mock.call('other_wordpress_path', nargs='?', help=mock.ANY)
	]
	parser.add_argument.assert_has_calls(parserCalls)
	group.add_argument.assert_has_calls(groupCalls)

@mock.patch('wpanalyser.analyser.is_wordpress')
@mock.patch('wpanalyser.analyser.os.path.exists')
@mock.patch('wpanalyser.analyser.os.makedirs')
@mock.patch('wpanalyser.analyser.find_wp_version')
@mock.patch('wpanalyser.analyser.download_wordpress')
@mock.patch('wpanalyser.analyser.unzip')
def test_process_wp_dirs(mock_unzip, mock_download_wp, mock_find_wp,
					mock_makedirs, mock_pathexists, mock_is_wordpress):
	args = mock.MagicMock()
	args.wordpress_path = 'wp'
	args.other_wordpress_path = False
	args.with_version = False

	mock_is_wordpress.side_effect = [False]
	wpPath, otherWpPath = wpa.process_wp_dirs(args)
	assert_false(wpPath)
	assert_false(otherWpPath)

	mock_is_wordpress.side_effect = [True, False]
	args.other_wordpress_path = 'owp'
	wpPath, otherWpPath = wpa.process_wp_dirs(args)
	assert_equal(wpPath, 'wp')
	assert_false(otherWpPath)

	mock_is_wordpress.side_effect = [True, True]
	wpPath, otherWpPath = wpa.process_wp_dirs(args)
	assert_equal(wpPath, 'wp')
	assert_equal(otherWpPath, 'owp')	

	mock_is_wordpress.return_value = True
	mock_is_wordpress.side_effect = None

	args.other_wordpress_path = False
	mock_pathexists.return_value = False
	mock_makedirs.side_effect = OSError
	wpPath, otherWpPath = wpa.process_wp_dirs(args)
	assert_equal(wpPath, 'wp')
	assert_false(otherWpPath)

	mock_makedirs.side_effect = None

	mock_find_wp.return_value = False
	wpPath, otherWpPath = wpa.process_wp_dirs(args)
	assert wpPath is not False
	mock_find_wp.assert_called_with(os.path.join(wpPath, wpa.WP_VERSION_FILE_PATH))
	assert_equal(wpPath, 'wp')
	assert_false(otherWpPath)

	args.with_version = '1.4.2'
	mock_download_wp.return_value = False, False
	wpPath, otherWpPath = wpa.process_wp_dirs(args)
	assert_equal(wpPath, 'wp')
	assert_false(otherWpPath)

	mock_download_wp.return_value = True, 'wp.zip'
	mock_unzip.return_value = False
	wpPath, otherWpPath = wpa.process_wp_dirs(args)
	assert_equal(wpPath, 'wp')
	assert_false(otherWpPath)

	mock_unzip.return_value = 'wp'
	wpPath, otherWpPath = wpa.process_wp_dirs(args)
	assert_equal(wpPath, 'wp')
	assert_equal(otherWpPath, p('wpa-temp/wp'))

