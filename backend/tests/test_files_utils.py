import pytest

from utils.files_utils import should_exclude_file, clean_path


def test_should_exclude_file_by_name():
    assert should_exclude_file('.gitignore')


def test_should_exclude_file_by_directory():
    assert should_exclude_file('node_modules/something.js')


def test_should_exclude_file_by_extension():
    assert should_exclude_file('image.png')


def test_should_not_exclude_normal_file():
    assert not should_exclude_file('src/app.py')


def test_clean_path_normalization():
    assert clean_path('/workspace/foo/bar.txt') == 'foo/bar.txt'
    assert clean_path('workspace/foo/bar.txt') == 'foo/bar.txt'
    assert clean_path('/foo/bar.txt') == 'foo/bar.txt'
