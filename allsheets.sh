LATEST="17"
MAINT="16"
VI_LATEST="20"
VI_MAINT="19"
CUR_RELEASE="1.36"
LAST_RELEASE="1.35"
python issueWriter.py -wn $CUR_RELEASE"_UI_TestSuite" -sn $CUR_RELEASE" Milestone Features" -r iqtools -al enhancement -el wontfix bug automated verified -m $LATEST -tc "#c6e0b4" -d \
-sn $LAST_RELEASE" Maint Features" -r iqtools -al enhancement -el wontfix automated verified   -m $MAINT -tc "#c6e0b4" -d \
-sn "VI "$CUR_RELEASE" Milestone Features" -r vantiq-issues -al enhancement -el wontfix automated Verified -m $VI_LATEST -tc "#c6e0b4" -d \
-sn "VI "$LAST_RELEASE" Maint Features" -r vantiq-issues -al enhancement -el wontfix automated Verified -m $VI_MAINT -tc "#c6e0b4" -d \
-sn $CUR_RELEASE" Milestone Bugs" -r iqtools -al -el enhancement wontfix automated verified  -m $LATEST -tc "#f4b084" -d \
-sn $LAST_RELEASE" Maint Bugs" -r iqtools -al -el enhancement wontfix automated verified  -m $MAINT -tc "#f4b084" -d \
-sn "VI "$CUR_RELEASE" Milestone Bugs" -r vantiq-issues -al -el enhancement wontfix automated Verified -m $VI_LATEST -tc "#f4b084" -d \
-sn "VI "$LAST_RELEASE" Maint Bugs" -r vantiq-issues -al -el enhancement wontfix automated Verified -m $VI_MAINT -tc "#f4b084" -d