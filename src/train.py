import logging
import cv2
import numpy
import cStringIO
import django.contrib.gis.geos.collections
from mapping.tilemanager import StaticMapGenerator
from mapping.osmmanager import OSMManager
from storage.storagemanager import getStorageManager

# This class generates the training samples using Bing Maps and OSM building data
# to be used to train the algorithm.
# 
# This class does NOT train the algorithm, just downloads and prepares the data
# 
# Positive sample = a building
# Negative sample = anything that's not a building (trees, water, etc)
class Train():

    def __init__(self):
        self.map_generator          = StaticMapGenerator([19]) # TODO: Assuming zoom level 19 is available
        self.osmmanager             = OSMManager()
        self.storagemanager         = getStorageManager()

    # Process a list of map tiles
    def processTiles(self, tiles):

        tile_count = 1

        for tile in tiles:

            min_lon, min_lat, max_lon, max_lat = [float(x) for x in tile]
            positive_images, negative_images = self.processTile(tile_count, min_lat, min_lon, max_lat, max_lon)

            # Write training data to file
            self.storagemanager.put("classifier_input", "positives_%s.dat" % tile_count, ''.join(positive_images),   overwrite=True)
            self.storagemanager.put("classifier_input", "negatives_%s.txt" % tile_count, '\n'.join(negative_images), overwrite=True)

            tile_count = tile_count + 1

    # Build training data using the rectangle created by the GPS coords min_lat, min_lon, max_lat, max_lon
    def processTile(self, tile_id, min_lat, min_lon, max_lat, max_lon):

        logging.info("Downloading satellite imagery for tile %s" % tile_id)

        tile_coords             = self.map_generator.coords_to_ltrb(((min_lat, min_lon),(max_lat, max_lon)), left=180, right=-180, top=180, bottom=-180)
        tile_image              = self.map_generator.get_tile_image(tile_coords)
        tile_image_filename     = ','.join(str(item) for item in tile_coords)
        tile_image_loc          = self.storagemanager.build_filename('bing_tiles', "%s.png" % (tile_image_filename))

        logging.info("Downloading OSM building data for tile %s" % tile_id)
        
        building_coords         = self._getExistingBuildingCoords(tile_coords)

        logging.info("Generating positive training data for tile %s" % tile_id)
        
        positive_images, positive_coords = self._getPositiveSamples(tile_image.size, building_coords)
        positive_images.insert(0, "%s\t" % tile_image_loc)

        logging.info("Generating negative training data for tile %s" % tile_id)
        
        # These next three lines assume that OSM building data is complete. If any buildings are
        # missing from the OSM data they will get included with the negative samples and negatively 
        # affect the training of the algorithm.
        
        # Change pixels of known houses to black so they don't get included in the negative output
        for positive_coord in positive_coords:
            tile_image.paste((0,0,0), positive_coord)
        # Generate negative training data
        negative_images = self._getNegativeSamples(tile_id, tile_image)

        # Print out some useful stats
        logging.info("Tile %s stats: Positive Images: %s, Negative Images: %s" % (tile_id, len(positive_images), len(negative_images)))

        return positive_images, negative_images

    # Get the coordinates for the buildings that already exist in OSM
    def _getExistingBuildingCoords(self, tile_coords):
        left, right, top, bottom = tile_coords
        return self.osmmanager.getBuildingData(left, right, top, bottom)

    # Get the positive training samples (i.e. the existing buildings in OSM)
    def _getPositiveSamples(self, tile_image_size, building_data):
        
        positive_images = []
        positive_coords = []

        # Loop though each building in the OSM data
        for building in building_data:
            positive_image = self._getPositiveSample(tile_image_size, building, positive_coords)
            if positive_image is not None:
                positive_images.append(positive_image)

        positive_images.insert(0, "%s\t" % len(positive_images))

        return (positive_images, positive_coords)

    def _getPositiveSample(self, tile_image_size, building, positive_coords):
        
         for building_lat_lng in building.coords:

            coords = []
            # Convert the lat, lon coords into x, y relative to the tile
            for lng, lat in building_lat_lng:
                coords.append(self.map_generator.x_y_for_lat_long(lat, lng))

            # Convert the x,y coords into left, top, right, bottom pixel locations
            ltrb = self.map_generator.coords_to_ltrb(coords, top = tile_image_size[1], left = tile_image_size[0], returnInt=True)

            positive_coords.append(ltrb)

            # Sometimes OSM returns buildings that start beyond the tile. Skip these.
            if ltrb[0] < 0 or ltrb[1] < 0 or ltrb[2] > tile_image_size[0] or ltrb[3] > tile_image_size[1]:
                return

            height = ltrb[3] - ltrb[1]
            width = ltrb[2] - ltrb[0]

            return "%i %i %i %i\t" % (ltrb[0], ltrb[1], width, height)

    # Split up the satellite image into squares to use as negative training samples
    def _getNegativeSamples(self, tile_id, tile_image):

        negative_images = []

        # Default to using a block size of 256 pixels (bing maps used 256 pixel blocks)
        SQUARE_SIZE = 256
        SQUARE_WIDTH = tile_image.size[0] / SQUARE_SIZE
        SQUARE_HEIGHT = tile_image.size[1] / SQUARE_SIZE

        i = 0
        while i<SQUARE_HEIGHT:
            j = 0
            while j<SQUARE_WIDTH:
                image_cropped = tile_image.crop((j*SQUARE_SIZE, i*SQUARE_SIZE, (j*SQUARE_SIZE)+(SQUARE_SIZE), (i*SQUARE_SIZE)+SQUARE_SIZE))
            
                output_img_bytes = cStringIO.StringIO()
                image_cropped.save(output_img_bytes, 'PNG')
                filename = self.storagemanager.put("negative_input", "%s_%s_%s_%s.png" % (SQUARE_SIZE, tile_id, i, j), output_img_bytes.getvalue())
                negative_images.append(filename)

                j += 1
            i += 1

        negative_images.append('\n')

        return negative_images