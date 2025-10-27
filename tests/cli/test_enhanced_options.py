"""Smoke tests for enhanced CLI options on download/magnet commands.

We don't execute full downloads here; we just validate option wiring and that
the commands parse and reach early paths without raising exceptions.
"""

from click.testing import CliRunner

from ccbt.cli.main import download, magnet


def test_download_parses_network_and_disk_options(tmp_path):
	runner = CliRunner()
	with runner.isolated_filesystem():
		# Create a tiny fake torrent file that will fail to parse later but tests option parsing
		open("fake.torrent", "wb").write(b"d4:infod5:fileslee")
		result = runner.invoke(
			download,
			[
				"fake.torrent",
				"--listen-port",
				"7001",
				"--max-peers",
				"100",
				"--pipeline-depth",
				"32",
				"--block-size-kib",
				"32",
				"--hash-workers",
				"2",
				"--disk-workers",
				"2",
				"--write-batch-kib",
				"64",
				"--write-buffer-kib",
				"512",
				"--enable-dht",
			],
		)
		# Will likely error due to invalid torrent file; assert the command handled parsing layer
		assert result.exit_code != 2, result.output  # not click usage error


def test_magnet_parses_options():
	runner = CliRunner()
	res = runner.invoke(
		magnet,
		[
			"magnet:?xt=urn:btih:0000000000000000000000000000000000000000",
			"--listen-port",
			"7002",
			"--enable-dht",
			"--use-mmap",
		],
	)
	# Magnet parsing path should handle errors gracefully
	assert res.exit_code in (0, 1), res.output


