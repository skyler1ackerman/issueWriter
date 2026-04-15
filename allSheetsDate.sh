DATE="7/30/2025"
ADD_TITLE="Post 7-30"
LATEST="30"
MAINT="31"
VI_LATEST="35"
VI_MAINT="34"
CUR_RELEASE="1.43"
LAST_RELEASE="1.42"
python issueWriter.py -wn "$ADD_TITLE""_UI_TestSuite" -sn "$ADD_TITLE"" Milestone Feat." -r iqtools -al enhancement -el wontfix bug automated verified -m $LATEST -tc "#c6e0b4" -d $DATE \
-sn "$ADD_TITLE"" Maint Feat." -r iqtools -al enhancement -el wontfix automated verified   -m $MAINT -tc "#c6e0b4" -d $DATE \
-sn "VI ""$ADD_TITLE"" Milestone Feat." -r vantiq-issues -al enhancement -el wontfix automated Verified -m $VI_LATEST -tc "#c6e0b4" -d $DATE \
-sn "VI ""$ADD_TITLE"" Maint Feat." -r vantiq-issues -al enhancement -el wontfix automated Verified -m $VI_MAINT -tc "#c6e0b4" -d $DATE \
-sn "$ADD_TITLE"" Milestone Bugs" -r iqtools -al -el enhancement wontfix automated verified  -m $LATEST -tc "#f4b084" -d $DATE \
-sn "$ADD_TITLE"" Maint Bugs" -r iqtools -al -el enhancement wontfix automated verified  -m $MAINT -tc "#f4b084" -d $DATE \
-sn "VI ""$ADD_TITLE"" Milestone Bugs" -r vantiq-issues -al -el enhancement wontfix automated Verified -m $VI_LATEST -tc "#f4b084" -d $DATE \
-sn "VI ""$ADD_TITLE"" Maint Bugs" -r vantiq-issues -al -el enhancement wontfix automated Verified -m $VI_MAINT -tc "#f4b084" -d $DATE