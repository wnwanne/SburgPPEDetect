import json
import boto3
import io
import numpy as np
from PIL import Image, ImageDraw, ExifTags, ImageColor, ImageFont


def detect_ppe(bucket_name, image_name, confidence, dest_bucket):
    # Implement AWS Services
    client = boto3.client('rekognition')
    # s3 = boto3.resource('s3')
    s3 = boto3.client("s3")

    # set colors and line width
    fill_green = '#00d400'
    fill_red = '#ff0000'
    fill_yellow = '#ffff00'
    line_width = 3
    mask_on = 'Mask is on properly'
    mask_not_on_properly = 'Please Fix Mask'
    mask_off = 'No Mask'

    # Download image from S3 as Bytes
    fileObj = s3.get_object(Bucket=bucket_name, Key=image_name)
    file_content = fileObj["Body"].read()

    # Open image from bytes to get dimensions
    image = Image.open(io.BytesIO(file_content))
    imgWidth, imgHeight = image.size
    draw = ImageDraw.Draw(image)

    # Call Rekogntion function, feed image as bytes
    response = client.detect_protective_equipment(Image={'Bytes': file_content})

    # for every person in the picture...
    for person in response['Persons']:

        found_mask = False

        # Check each body part for PPE items...
        for body_part in person['BodyParts']:
            ppe_items = body_part['EquipmentDetections']

            for ppe_item in ppe_items:
                # found a mask
                if ppe_item['Type'] == 'FACE_COVER':
                    fill_color = fill_green
                    found_mask = True
                    # check if mask covers face
                    if ppe_item['CoversBodyPart']['Value'] == False:
                        fill_color = fill = '#ff0000'
                    # draw bounding box around mask
                    box = ppe_item['BoundingBox']
                    left = imgWidth * box['Left']
                    top = imgHeight * box['Top']
                    width = imgWidth * box['Width']
                    height = imgHeight * box['Height']
                    points = (
                        (left, top),
                        (left + width, top),
                        (left + width, top + height),
                        (left, top + height),
                        (left, top)
                    )
                    draw.line(points, fill=fill_color, width=line_width)
                    draw.text((left, top + height), mask_on, fill=fill_color, width=line_width)

                    # Check if confidence is lower than supplied value
                    if ppe_item['CoversBodyPart']['Confidence'] < confidence:
                        # draw warning yellow bounding box within face mask bounding box
                        offset = line_width + line_width
                        points = (
                            (left + offset, top + offset),
                            (left + width - offset, top + offset),
                            ((left) + (width - offset), (top - offset) + (height)),
                            (left + offset, (top) + (height - offset)),
                            (left + offset, top + offset)
                        )
                        draw.line(points, fill=fill_yellow, width=line_width)
                        draw.text((left, top + height), mask_not_on_properly, fill=fill_yellow, width=line_width)

        if found_mask == False:
            # no face mask found so draw red bounding box around body
            box = person['BoundingBox']
            left = imgWidth * box['Left']
            top = imgHeight * box['Top']
            width = imgWidth * box['Width']
            height = imgHeight * box['Height']
            points = (
                (left, top),
                (left + width, top),
                (left + width, top + height),
                (left, top + height),
                (left, top)
            )
            draw.line(points, fill=fill_red, width=line_width)
            draw.text((left, top + height), mask_off, fill=fill_red, width=line_width)

    # saving image in memory
    in_mem_file = io.BytesIO()
    image.save(in_mem_file, format=image.format)
    in_mem_file.seek(0)

    print("uploading image")
    # Upload image to s3
    s3.upload_fileobj(in_mem_file, dest_bucket, 'ppe-detected-' + image_name)


def lambda_handler(event, context):
    # Get the bucket and image from the event
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    image_name = str(event['Records'][0]['s3']['object']['key'])

    # Give confidence and destination bucket
    confidence = 80
    dest_bucket = ''

    # Call detect function
    detect_ppe(bucket_name, image_name, confidence, dest_bucket)
