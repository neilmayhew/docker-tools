#!/usr/bin/env python

"""Show an image and its parent layers"""

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
		size   = info["Size"]
		cmds   = commands(info)

		print "%-14s %-20s %10d %s" % (id[:14], last(labels), size, last(cmds))

def main():

	parser = argparse.ArgumentParser(description="Analyze docker image layers")
	parser.add_argument("image", help="The image to be analyzed")

	args = parser.parse_args()

	try:
		show(args.image)

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
