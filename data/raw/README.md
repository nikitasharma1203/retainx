# Raw data

Not committed. Download **Online Retail II** from the UCI repository
(search "UCI Online Retail II"). It comes as one xlsx with two sheets
(2009-2010 and 2010-2011). A Kaggle CSV copy also works.

Then:

    make up
    make profile FILE=data/raw/online_retail_II.xlsx
    make load FILE=data/raw/online_retail_II.xlsx

Check the date range and column names in the file you actually downloaded.
