import sys
import logging
import argparse
import hashlib
from train import Train
from detect import Detect
from storage.storagemanager import initStorageManager, getStorageManager

# Logging setup start
logger 	= logging.getLogger('buildingdetector')
root = logging.getLogger()
root.setLevel("INFO")
ch = logging.StreamHandler(sys.stdout)
ch.setLevel("INFO")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)
# Logging setup end


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('--coords',		'--coords', 	type=str, 	required=True, nargs = '*', action='append')
	parser.add_argument('--type',		'--type', 		type=str, 	required=True, choices=["train", "detect"])
	parser.add_argument('--train_id',	'--train_id', 	type=str, 	required=False)
	args = parser.parse_args()

	# The train_id variable is a hash of  min_lat, min_lon, max_lat, max_lon.
	# It allows different training sets to be run and stored seperately
	if args.train_id is None:
		if args.type == 'detect':
			logger.error('train_id must be set to the ID printed out at the training stage')
			sys.exit()
		hash_object = hashlib.md5(str(args.coords))
		train_id = hash_object.hexdigest()
	else:
		train_id = args.train_id

	logger.info('Using training ID: %s' % train_id)

	initStorageManager(train_id)

	# Loop through each GPS coordinate set provided
	if args.type == 'train':
		train = Train()
		train.processTiles(args.coords)
	if args.type == 'detect':
		detect = Detect()
		detect.processTiles(args.coords)

if __name__ == "__main__":
    main()