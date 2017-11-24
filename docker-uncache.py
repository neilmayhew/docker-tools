#!/usr/bin/env python

"""Remove an image and some of its cached parent layers"""

from exceptions import RuntimeError
import argparse
import json
import re
import subprocess
import sys

# Note: shelling out to "docker inspect" to avoid a dependency on python-docker

def inspect(image):
	process = subprocess.Popen(["docker", "inspect", image],
				stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	(out, err) = process.communicate()
	return (out, err, process.returncode)

def info(image):
	(out, err, code) = inspect(image)
	sys.stderr.write(err)
	if code:
		raise RuntimeError("Failed to inspect %s" % image)
	return json.loads(out)[0]

def exists(image):
	(_, _, code) = inspect(image)
	return code == 0

def hierarchy(image):
	while True:
		if not image:
			return

		layer = info(image)

		if not layer:
			return

		yield layer

		image = layer["Parent"]

def commands(l):
	return map(lambda s: re.sub(r'\s+', ' ', s), l["ContainerConfig"]["Cmd"])

def describe(l):
	if l["RepoTags"]:
		return " ".join(l["RepoTags"])
	else:
		return l["Id"][:14] + " " + commands(l)[-1]

def indexIf(pred, seq):
	for (i, x) in enumerate(seq):
		if pred(x):
			return i
	return None

def execute(cmd):
	print " ".join(cmd)
	if dry_run:
		return
	if subprocess.call(cmd) != 0:
		raise RuntimeError("Command failed:", *cmd)

class LayersException(Exception):
	def __init__(self, reason, layers):
		self.reason = reason
		self.layers = layers

def show(image):

	def last(lst):
		return lst and lst[-1] or ""

	for info in hierarchy(image):
		id     = info["Id"]
		labels = info["RepoTags"]
		cmds   = commands(info)

		print "%-14s %-20s %s" % (id[:14], last(labels), last(cmds))

def uncache(image, test, exclusive=False):

	def testlayer(layer):
		return filter(test, commands(layer))

	layers = list(hierarchy(image))

	if not layers:
		raise RuntimeError("No layers found")

	if len(layers[0]["RepoTags"]) > 1:
		raise LayersException("Image has multiple tags", layers[:1])

	limit = indexIf(testlayer, layers)

	if limit is None:
		raise RuntimeError("No matching layer")

	if not exclusive:
		limit += 1

	strip = layers[:limit]

	if not strip:
		raise RuntimeError("No layers to uncache")

	ancestors = filter(lambda i: i["RepoTags"], strip[1:])

	if ancestors:
		raise LayersException("Tagged ancestors are preventing uncaching", ancestors)

	anchor = strip[-1]["Parent"]

	if anchor:
		execute(["docker", "tag", anchor[:14], "uncache:keep"])

	execute(["docker", "rmi", image])

	if dry_run:
		return

	remaining = filter(lambda i: exists(i["Id"]), strip)

	if remaining:
		raise LayersException("Some layers were not pruned", remaining)

def main():

	parser = argparse.ArgumentParser(description="Uncache docker image layers")
	parser.add_argument("-x", "--exclusive", action="store_true", help="Don't uncache the matched layer")
	parser.add_argument("-n", "--dry-run",   action="store_true", help="Just print what would be done")
	parser.add_argument("-l", "--layers",    action="store_true", help="Just show the image layers (command is ignored)")
	parser.add_argument("image",   help="The image to be rebuilt")
	parser.add_argument("command", help="A regexp specifying the command of the lowest layer to be uncached")

	args = parser.parse_args()

	global dry_run; dry_run = args.dry_run

	try:
		if args.layers:
			show(args.image)
		else:
			uncache(args.image, lambda c: re.search(args.command, c), args.exclusive)

	except LayersException as e:
		print >> sys.stderr, e.reason
		for l in e.layers:
			print >> sys.stderr, "  " + describe(l)
		sys.exit(1)

	except RuntimeError as e:
		print >> sys.stderr, " ".join(e.args)
		sys.exit(2)

if __name__ == "__main__":
	main()
