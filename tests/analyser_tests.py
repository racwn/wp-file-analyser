from nose.tools import *
import wpanalyser.analyser as wpa
import mock
import unittest
import os
from requests.exceptions import HTTPError
from StringIO import StringIO


"""
Tests should be run from top level project folder using 'nosetests'
"""
def test_file_open():
	m = mock.mock_open()
	with mock.patch('wpanalyser.analyser.open', m, create=True):
		wpa.open_file('foo', 'r')
		m.assert_called_with('foo', 'r')

	m.side_effect = IOError
	with mock.patch('wpanalyser.analyser.open', m, create=True):
		res = wpa.open_file('foo', 'r')
		m.assert_called_with('foo', 'r')
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

	mock_zip.side_effect = wpa.zipfile.BadZipfile
	res = wpa.unzip('zipFile.zip', '/')
	assert_false(res)


@mock.patch('wpanalyser.analyser.os.path.isfile')
@mock.patch('wpanalyser.analyser.open_file')
@mock.patch('wpanalyser.analyser.requests')
def test_download_file(mock_requests, mock_open_file, mock_isfile):
	mockFile = mock.MagicMock(spec=file)
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
	assert_false(res)

	mock_isfile.return_value = False
	mock_open_file.return_value = False
	res = wpa.download_file("http://file.com", ".", "cannotcreatefile.txt")
	assert_false(res)

	response.raise_for_status.side_effect = HTTPError
	res = wpa.download_file("http://file.com", ".", "file.txt")
	response.raise_for_status.assert_called_with()
	assert_false(res)


@mock.patch('wpanalyser.analyser.os.walk')
def test_search_dir_for_ext(mock_walk):
	mock_walk.return_value = []
	res = wpa.search_dir_for_ext('not a dir', '.txt')
	mock_walk.assert_called_with('not a dir')
	
	mock_walk.return_value = [
		('/foo', ('/bar',), ('test.txt', 'temp.doc',)),
		('/foo/bar', (), ('test2.txt',)),
	]
	res = wpa.search_dir_for_ext('/foo', '.txt')
	s = {'/foo/test.txt', '/foo/bar/test2.txt'}
	assert_equal(len(res), 2, "Returned set is the wrong size")
	assert_equal(s, res, "Wrong files are returned")


@mock.patch('wpanalyser.analyser.os.path.abspath')
def test_is_subdir(mock_abspath):
	mock_abspath.side_effect = ['/abs/path/sub/file.txt', '/abs/path']
	res = wpa.is_subdir('path/sub/file.txt', 'path')
	assert_true(res)

	mock_abspath.side_effect = ['/abs/path/sub/file.txt', 'abs/not/same/path']
	res = wpa.is_subdir('path/sub/file.txt', 'not/same/path')
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
def test_find_plugin_version(mock_open_file):
	mockFile = mock.MagicMock(spec=file)
	mock_open_file.return_value = mockFile
	mockFile.__iter__ = mock.MagicMock(return_value=iter(['abc\n', 'def\n', 'ghi\n']))
	res = wpa.find_plugin_version('readme.txt')
	mock_open_file.assert_called_with('readme.txt', 'r')
	assert_false(res)

	mockFile.__iter__ = mock.MagicMock(return_value=iter(['abc\n', 'Stable tag: 1.2.3\n', 'ghi\n']))
	res = wpa.find_plugin_version('readme.txt')
	mock_open_file.assert_called_with('readme.txt', 'r')
	assert_equal(res, '1.2.3')


@mock.patch('wpanalyser.analyser.open_file')
def test_find_wp_version(mock_open_file):
	mockFile = mock.MagicMock(spec=file)
	mock_open_file.return_value = mockFile
	mockFile.__iter__ = mock.Mock(return_value=iter(['abc', 'def', 'ghi']))
	res = wpa.find_wp_version('file.txt')
	mock_open_file.assert_called_with('file.txt', 'r')
	assert_false(res)

	mockFile.__iter__ = mock.Mock(return_value=iter(['abc', "$wp_version == '1.2.3'", 'ghi']))
	res = wpa.find_wp_version('file.txt')
	assert_equal(res, '1.2.3')

	mock_open_file.return_value = False
	res = wpa.find_wp_version('notafile.txt')
	assert_false(res)


@mock.patch('wpanalyser.analyser.download_file')
def test_download_wordpress(mock_download_file):
	mock_download_file.return_value = True
	res, fileName = wpa.download_wordpress('1.4.3', 'tmp')
	mock_download_file.assert_called_with(wpa.WP_PACKAGE_ARCHIVE_LINK + '1.4.3.zip', 
										  'tmp', 'wordpress_1.4.3.zip')
	assert_true(res)
	assert_equal(fileName, 'tmp/wordpress_1.4.3.zip')


@mock.patch('wpanalyser.analyser.download_file')
@mock.patch('wpanalyser.analyser.unzip')
@mock.patch('wpanalyser.analyser.os.remove')
def test_get_plugin(mock_remove, mock_unzip, mock_download_file):
	mock_download_file.return_value = True
	mock_unzip.return_value = 'wp/wp-content/plugins/plugin'
	res = wpa.get_plugin('plugin', '1.2.3', 'wp')
	mock_download_file.assert_called_with(
					'https://downloads.wordpress.org/plugin/plugin.1.2.3.zip',
					wpa.TEMP_DIR,
					'plugin.1.2.3.zip')
	mock_unzip.assert_called_with(os.path.join(wpa.TEMP_DIR, 'plugin.1.2.3.zip'), 'wp/wp-content/plugins')
	mock_remove.assert_called_with(os.path.join(wpa.TEMP_DIR, 'plugin.1.2.3.zip'))
	assert_equal(res, 'wp/wp-content/plugins/plugin')


@mock.patch('wpanalyser.analyser.os.path.isfile')
def test_is_wordpress(mock_isfile):
	mock_isfile.side_effect = [True, True, True, False]
	res = wpa.is_wordpress('/test')
	assert_false(res)

	mock_isfile.side_effect = [True, True, True, True]
	res = wpa.is_wordpress('/test')
	assert_true(res)


@mock.patch('wpanalyser.analyser.find_plugin_version')
@mock.patch('wpanalyser.analyser.os.walk')
def test_find_plugins(mock_walk, mock_find_plugin_version):
	mock_walk.return_value = iter([
			('plugins', ('plugin1', 'plugin2'), ('plugin1.php', 'plugin2.php')),
			('plugins/plugin1', (), ('plugin1.php')),
			('plugins/plugin2', (), ('plugin2.php'))
		])
	mock_find_plugin_version.side_effect = ['1.2.3','1.2.4']
	res = wpa.find_plugins('wp')
	mock_walk.assert_called_with('wp/wp-content/plugins')
	calls = [
		mock.call('wp/wp-content/plugins/plugin1/readme.txt'),
		mock.call('wp/wp-content/plugins/plugin2/readme.txt'),
	]
	mock_find_plugin_version.assert_has_calls(calls)
	assert_equal(res, [
		{'name': 'plugin1', 'version': '1.2.3'}, 
		{'name': 'plugin2', 'version': '1.2.4'}
	])


@mock.patch('wpanalyser.analyser.ignored_file')
@mock.patch('wpanalyser.analyser.os.path.isdir')
def test_analyze(mock_isdir, mock_ignored_file):
	mock_isdir.return_value = False
	firstDcRes = mock.MagicMock()
	firstDcRes.left = 'some/path'
	firstDcRes.right = 'other/path'
	firstDcRes.diff_files = ['changed1.txt', 'changed2.txt']
	firstDcRes.left_only = ['extra1.txt', 'extra2.txt']
	firstDcRes.right_only = ['missing1.txt']
	secondDcRes = mock.MagicMock()
	secondDcRes.left = 'some/path/sub'
	secondDcRes.diff_files = ['changed3.txt']
	secondDcRes.left_only = ['extra3.txt']
	firstDcRes.subdirs.values.return_value = [secondDcRes]
	secondDcRes.subdirs.values.return_value = []
	mock_ignored_file.side_effect = [False, False, True] # ignore files in the /sub directory
	diff, extra, missing = wpa.analyze(firstDcRes, 'wp')
	diffCmp =  {'some/path/changed1.txt', 'some/path/changed2.txt', 'some/path/sub/changed3.txt' }
	extraCmp = {'some/path/extra1.txt', 'some/path/extra2.txt'}
	missingCmp = {'other/path/missing1.txt'}
	assert_equal(diff, diffCmp)
	assert_equal(extra, extraCmp)
	assert_equal(missing, missingCmp)

@mock.patch('wpanalyser.analyser.sys.stdout', new_callable=StringIO)
def test_print_analysis(mock_stdout):
	diff = ['diff1.txt', 'diff2.txt']
	extra = ['extra1.txt', 'extra2.txt']
	missing = ['missing1.txt', 'missing2.txt']
	extraPhp = ['extra1.php', 'extra2.php']
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

	os.makedirs.side_effect = None
	mock_find_wp.return_value = False
	wpPath, otherWpPath = wpa.process_wp_dirs(args)
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
	assert_equal(otherWpPath, 'wpa-temp/wp')

