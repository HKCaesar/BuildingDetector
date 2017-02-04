import os
import logging

class StorageManager():
	def initalise(self, output_id, manager=None):
		self.output_id 	= output_id
		if manager is None:
			self.manager = LocalStorage(self.output_id)
		else:
			self.manager = manager

storageManager = StorageManager()

def initStorageManager(output_id, manager=None):
		storageManager.initalise(output_id, manager)

def getStorageManager():
		return storageManager.manager
	
class AbstractStorage:
	def __init__(self):
		pass

	def get(self, type, locator):
		"""must be implemented by subclass"""
		raise NotImplementedError

	def put(self, type, locator, obj, overwrite=False):
		"""must be implemented by subclass"""
		raise NotImplementedError

class LocalStorage(AbstractStorage):

	def __init__(self, output_id):
		self.output_id 	= output_id

	def build_filename(self, obj_type, locator):
		if obj_type not in ["bing_raw"]:
			filename = os.path.abspath(os.path.join(os.path.dirname(__file__), "../output/%s/%s/%s" % (obj_type, self.output_id, locator)))
		else:
			filename = os.path.abspath(os.path.join(os.path.dirname(__file__), "../cache/%s/%s" % (obj_type, locator)))

		return filename

	def get(self, obj_type, locator):
		filename = self.build_filename(obj_type, locator)
		if not os.path.isfile(filename):
			return None

		with open(filename) as f:
			data = f.read()
		return data

	def put(self, obj_type, locator, obj, overwrite=False):

		filename = self.build_filename(obj_type, locator)

		if not os.path.exists(os.path.dirname(filename)):
			try:
				os.makedirs(os.path.dirname(filename))
			except Exception, e:
				logging.warn('Error creating directory: %s' % e)
				pass

		if obj:
			if os.path.isfile(filename) and overwrite is False:
				return filename
			else:
				out_file = file(filename, "w")
				out_file.write(obj)
				out_file.flush()
				out_file.close()

		return filename
