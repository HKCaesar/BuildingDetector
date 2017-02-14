# Introduction

This program can be used to train a Haar Cascade to find buildings in satellite images.

There are three steps:

1. Gather the training data
2. Train the cascade
3. Run the trained cascade against target data

To gather the training data, all you need is the GPS coordinates of an area in OpenStreetMap that already contains buildings. 

The program will download the satellite data for that area and then download the existing buildings from OSM. It will use these buildings as positive training samples and the background (roads, trees, etc) as negative training samples.

You will get a much better detection rate if you pick a training area that has all the buildings inputted into OSM.

Tip: You can find GPS coordinates easily by using Bing Maps and right-clicking on an area on the map.

After the training data has been gathered and the cascade has been trained, you can use it to detect buildings. All you need is the GPS coordinates of the area you want to search.

Tip: You will get a better detection rate if you pick an area in the same town / country as the one your trained in, since the buildings will be very similar.

# Installation

This was run on a fresh c4.xlarge AWS instance with the stock Ubuntu image.

##Install Dependencies

```bash
sudo apt-get update 
sudo apt-get install python-pip python-shapely binutils libproj-dev gdal-bin cmake
```

## Install OpenCV

(Need to compile OpenCV from source as the built-in package is old and buggy)

```bash
git clone -b 3.2.0 https://github.com/opencv/opencv.git
cd opencv
mkdir release && cd release
cmake -D CMAKE_BUILD_TYPE=RELEASE -D CMAKE_INSTALL_PREFIX=/usr/local ..
make
sudo make install
```

## Install BuildingDetector

```bash
cd ~
git clone https://github.com/philhunt/BuildingDetector.git
cd BuildingDetector/src/
sudo pip install -r requirements.txt
```

# Example Usage

In the examples below, we are training against a small area of north Ottawa and running the trained cascade against a small area in south Ottawa.

The detection rate is on the low side (60%-70%) due to the small training area.

You specify an area by suppling two GPS coordinates. These two coordinates form a rectangle (i.e. the first coordinate is the top-left of the rectangle, and the second coordinate is the bottom right of the rectangle).

Tip: You can provide multiple GPS coordinate values to these programs. Let say you want to train the algorithm on ten different areas in Ottawa - you just provide ten sets of GPS coordinates which form ten different rectangles. This is very useful when you want to use lots of different areas to train the algorithm. The more data the training algorithm gets, the more accurate it is. 


## Gather Training Data

Tip: Keep a note of the training ID printed out when this first runs. You will need it for the next two stages.

You should provide two GPS coordinates which create a rectangle for the program to use. In this example, we use (45.399525, -75.759344 ) and (45.391148, -75.728144). The values are entered as one string, space separated.

You can provide as many GPS rectangles as you like, just add another '--coords ' variable to the command. The more training data, the better.

```bash
python ./main.py --type train --coords 45.399525 -75.759344 45.391148 -75.728144
```

## Train the cascade 

Tip: If this stage crashes with an OutOfMemory error, change the precalcIdxBufSize and precalcValBufSize variables in train.sh to equal half of the available system memory.

Change TRAIN_ID to the training ID printed out when the train script was run. This should take less than a minute on a c4.xlarge AWS instance. If you used a large training area, this will take much longer (hours or days)

```bash
./train.sh TRAIN_ID
```

## Run the trained cascade

Tip: If you get too many / too few buildings detected, look at the top of detect.py to change the sensitivity of the trained cascade then re-run this step.

Change TRAIN_ID to the training ID printed out when the first stage was run. 

You should provide two GPS coordinates which create a rectangle for the program to use. In this example, we use (45.39690, -75.66622) and (45.38914,-75.64886). The values are entered as one string, comma separated.

You can provide as many GPS rectangles as you like, just add another '--coords ' variable to the command.

```bash
python ./main.py --type detect --coords 45.39690 -75.66622 45.38914 -75.64886 --train_id TRAIN_ID
```

This step will output an image with the detected buildings overlaid and a XML file which can be loaded into JOSM.

Output data will be written to BuildingDetector/src/output/detector_output/TRAIN_ID/

# Known Issues

Map areas are processed as a single image - processing a very large area will probably cause this to crash (untested). If this is the case, just spilt up the area into chunks by specifying multiple GPS coordinates using the '--coords' argument

# Troubleshooting

The following error means you entered the wrong train_id:

```bash
cv2.error: /home/ubuntu/opencv/modules/objdetect/src/cascadedetect.cpp:1681: error: (-215) !empty() in function detectMultiScale
```

# Further Reading:
http://coding-robin.de/2013/07/22/train-your-own-opencv-haar-classifier.html
http://docs.opencv.org/2.4/doc/user_guide/ug_traincascade.html
