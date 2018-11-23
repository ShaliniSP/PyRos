# Board-Game-Analysis
This repository contains 2 main datasets and a lot of sampled datasets.
The first datasets give information regarding the different board games along with their descriptions.
The second gives information about the user, game and rating.

## To run Collaborative Filtering:
*Open the Colab Folder
*The file present on the google drive - ratings.csv, is passed to the PreprocessedData.Rmd, as a result of which preprocessed_ratings.csv is formed. Which then splits to give test_data.csv and train_data.csv
*For model purpose, download the collab_test.csv and collab_train.csv
*Make the changes in file path while loading the data set. Run the Collaborative_Filtering.ipynb


## To run Content Based Filtering:
*Open the Content Based Filtering Folder.
*Download the datasets in that folder.
*Open both the R Markdowns and set working directory to your working directory.
*Run MakingGameFeatures.Rmd first.
*Then run ContentBasedFiltering.Rmd
ContentBasedFiltering.Rmd takes a while to run
