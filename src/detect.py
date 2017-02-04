import logging
import cv2
import numpy 
import math
from PIL import ImageDraw
from shapely.geometry import LineString
from mapping.tilemanager import StaticMapGenerator
from mapping.osmmanager import OSMManager
from storage.storagemanager import getStorageManager

class Detect:

    # The following class variables all control how sensitive the detector is
    # Very sensitive = more positives but more false positives
    # Less sensitive = less positives but less false positives

    # The sensitivity of the detector
    MIN_NEIGHBORS   = 2     # Reduce to make more sensitive (min value 2)
    SCALE_FACTOR    = 2   # Recuce to make more sensitive (min value 1.1)

    # The maximum width and height of any one building
    MAX_HEIGHT      = 200
    MAX_WIDTH       = 200
    MIN_HEIGHT      = 50
    MIN_WIDTH       = 50

    # Turns on a basic line filter. Any 'dection' without a strong line is
    # removed (on the basis that a building will have at least one strong line)
    # This is *very* simple and so will not always work - hence diabled by default.
    LINE_FILTER     = False
    LINE_THRESHOLD  = 30    # Reduce to make less sensitive (lets more detections through)
    MIN_LINE_LENGTH = 20    # Reduce to make less sensitive (lets more detections through)

    def __init__(self):
        self.map_generator  = StaticMapGenerator([19]) # TODO: Assuming zoom level 19 is available
        self.osmmanager     = OSMManager()
        self.storagemanager = getStorageManager()

    def processTiles(self, tiles):
        tile_count = 1

        for tile in tiles:

            min_lon, min_lat, max_lon, max_lat = [float(x) for x in tile]
            self.processTile(tile_count, min_lat, min_lon, max_lat, max_lon)

            tile_count = tile_count + 1

    def processTile(self, tile_id, min_lat, min_lon, max_lat, max_lon):

        logging.info("Downloading satellite imagery for tile %s" % tile_id)

        tile_coords             = self.map_generator.coords_to_ltrb(((min_lat, min_lon),(max_lat, max_lon)), left=180, right=-180, top=180, bottom=-180)
        tile_image              = self.map_generator.get_tile_image(tile_coords)

        logging.info("Running detector for tile %s" % tile_id)

        buildings               = self._findBuildings(tile_image)

        logging.info("Detected %i buildings for tile %s" % (len(buildings), tile_id))

        buildings                = self._filterBuildings(tile_image, buildings)

        logging.info("%i buildings after filtering for tile %s" % (len(buildings), tile_id))

        output_data              = self._getOutputData(tile_coords, buildings)

        # Draw detected buildings onto output satellite image
        draw                    = ImageDraw.Draw(tile_image)
        for detection in buildings:
            draw.rectangle([detection[0], detection[1], detection[0]+detection[2], detection[1]+detection[3]], None, (0, 255, 0))

        logging.info("Writing data to output folder for tile %s" % tile_id)

        # Generate the output filename (the search GPS coords concated together)
        filename        = ','.join(str(item) for item in tile_coords)

        # Output JSOM XML file
        self.storagemanager.put("detector_output", "%s.xml" % filename, output_data)

        # Output satellite image
        img_filename    = self.storagemanager.build_filename("detector_output", "%s.png" % filename)
        tile_image.save(img_filename, "PNG")

    # Runs the generated cascade against the satellite image
    def _findBuildings(self, image): 
        open_cv_image  = numpy.array(image) 

        # Load the previously generated cascade
        raw_cascade = self.storagemanager.build_filename("classifier_output", "cascade.xml")
        cascade     = cv2.CascadeClassifier(raw_cascade)

        return cascade.detectMultiScale(
            open_cv_image, 
            scaleFactor=self.SCALE_FACTOR, 
            minNeighbors=self.MIN_NEIGHBORS
            )

    def _filterBuildings(self, image, buildings):
        filtered_buildings = []
        for building_coords in buildings:
            filtered_building = self._filterBuilding(image, building_coords)
            if filtered_building is not None:
                filtered_buildings.append(filtered_building)
        return filtered_buildings

    # Remove large and small detections and optionally runs the line filter
    def _filterBuilding(self, image, building_coords):
        # Skip really big squares (usually a false positive)
        left, top, width, height = building_coords
        if width > self.MAX_WIDTH or height > self.MAX_HEIGHT:
            return

        if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
            return

        if self.LINE_FILTER == True:
            building_image  = image.crop((left, top, left+width, top+height)).copy()

            if self._isLinesInImage(building_image) == False:
                return

        return building_coords

    # Generates the XML output that can be loaded into JSOM
    def _getOutputData(self, tile_coords, building_data):

        minlat = tile_coords[1]
        minlon = tile_coords[0]
        maxlat = tile_coords[3]
        maxlon = tile_coords[2]

        output_data = []

        for building in building_data:
            nodes = []
            nodes.append(self.map_generator.lat_long_for_x_y(building[0], building[1]))
            nodes.append(self.map_generator.lat_long_for_x_y(building[0]+building[2], building[1]+building[3]))

            output_data.append(nodes)

        output_xml = self.osmmanager.generateOutputXml(minlat, minlon, maxlat, maxlon, output_data)

        return output_xml

    # Calculates if a straight line is in a given image
    def _isLinesInImage(self, image):
        
        # Convert RGB image to a numpy grayscale
        open_cv_orig_image = numpy.array(image)
        open_cv_orig_image = open_cv_orig_image[:, :, ::-1]
        gray = cv2.cvtColor(open_cv_orig_image, cv2.COLOR_BGR2GRAY)

        # Use two different types of bluring on the image to remove noise
        gBlur = cv2.GaussianBlur(gray, (3, 3), 0)
        mBlur = cv2.medianBlur(gBlur, ksize = 7)

        # Use a combination of canny and hough lines to find straight lines in the image
        th, bw = cv2.threshold(mBlur, 50, 150, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

        # Start with the least sensitive detector and keep going until lines are found
        for aperture in range(3, 8, 2):
            canny = cv2.Canny(mBlur, th/2, th, apertureSize = aperture, L2gradient=True)
            lines = cv2.HoughLinesP(canny, rho = 1, theta = math.pi / 180, threshold = self.LINE_THRESHOLD, minLineLength = self.MIN_LINE_LENGTH, maxLineGap = 0)

            # Keep going if we find < 2 lines
            if lines is not None and len(lines[0]) > 0:
                break

        if lines is not None and len(lines[0]) > 0:
            return True

        return False