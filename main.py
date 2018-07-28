#!/usr/bin/env python3
"""
This script loads the data from source(s) provides under the source folder and
plots the price trend of different film cameras.
"""

import glob
import pandas as pd


class Data:
    """
    Data object that obtains information about the camera records.
    """

    def __init__(self, record_folder):
        record_files = glob.glob(record_folder + "/*.csv")
        self.record = pd.concat(
            [
                pd.read_csv(
                    f, header=None,
                    names=["name", "price", "source", "author", "time", "url"]
                )
                for f in record_files
            ]
        ).reset_index()

        # Reformats the record name
        self.record.name = self.record.name.str.lower()
        self.record.name = self.record.name.str.replace("[^a-z0-9 ]", "")
        self.record.name = self.record.name.str.strip()

    def search(self, model_name):
        """
        Searches the entries of the given model name.
        """

        # Lowers the case and removes hyphens
        keywords = [
            k.replace("-", "")
            for k in model_name.lower().replace("[^a-z0-9 ]", "").split()
        ]

        # Finds out the fields that matches all the keywords
        matches = self.record.name.str.contains(keywords[0])
        for keyword in keywords:
            matches = self.record.name.str.contains(keyword)

        return self.record[matches == True].sort_values("time")


def main():
    """
    Main function of this script.
    """
    data = Data("./source/ptt/records")
    camera_list = __read_camera_list()
    for camera_model in camera_list:
        camera_data = data.search(camera_model)
        plot(camera_model, camera_data)


def __read_camera_list():
    with open("camera.txt") as fin:
        return [line.strip() for line in fin.readlines()]


def plot(camera_model, camera_data):
    """
    Plots the price trend of a camera model.
    """
    print("Camera Model: %s" % camera_model)
    print(camera_data)
    if camera_data.size == 0:
        print("Insufficient data for %s, skipped" % camera_model)
        return
    fig = camera_data.plot("time", "price").get_figure()
    fig.savefig("plot/" + camera_model + ".jpg")


if __name__ == "__main__":
    main()
