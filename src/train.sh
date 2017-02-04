#!/bin/sh

# The training ID
OUTPUT_ID=$1

cd output/classifier_input/$OUTPUT_ID/

find . -type f -name 'positives_*' -exec cat {} + > positives.dat
find . -type f -name 'negatives_*' -exec cat {} + > negatives.txt

# Calulate the number of positive and negative images 
POS_NUM=$(< positives.dat tr -dc \\t | wc -c)
NEG_NUM=$(wc -l < "negatives.txt")

# Convert the positive image samples into vec format
opencv_createsamples -info positives.dat -w 24 -h 24 -vec positives.vec -num $POS_NUM

# Create the output directories
mkdir -p ../../classifier_output/$OUTPUT_ID/

# BUG (opencv): Only use 90% of the positive samples (crashes otherwise)
TOTAL_POS_TRAIN=$(($POS_NUM-$(($POS_NUM/10))))

# Train the algorithm
# REMEMBER: Change precalcValBufSize and precalcIdxBufSize to half the size of the system memory (in MB)
opencv_traincascade -data ../../classifier_output/$OUTPUT_ID -vec positives.vec\
  -bg ../../classifier_input/$OUTPUT_ID/negatives.txt\
  -numStages 20 -minHitRate 0.999 -maxFalseAlarmRate 0.5 -numPos $TOTAL_POS_TRAIN\
  -numNeg $NEG_NUM -w 24 -h 24 -mode ALL -precalcValBufSize 7500\
  -precalcIdxBufSize 7500 -numThreads 8 -featureType LBP