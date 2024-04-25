LATEST="23"
MAINT="22"
VI_LATEST="26"
VI_MAINT="25"
CUR_RELEASE="1.39"
LAST_RELEASE="1.38"
python issueWriter.py -wn $CUR_RELEASE"_UI_TestSuite" -sn $CUR_RELEASE" Milestone Features" -r iqtools -al enhancement -el wontfix duplicate bug automated verified -m $LATEST -tc "#c6e0b4" -d \
-sn $LAST_RELEASE" Maint Features" -r iqtools -al enhancement -el wontfix duplicate automated verified   -m $MAINT -tc "#c6e0b4" -d \
-sn "VI "$CUR_RELEASE" Milestone Features" -r vantiq-issues -al enhancement -el wontfix duplicate automated Verified -m $VI_LATEST -tc "#c6e0b4" -d \
-sn "VI "$LAST_RELEASE" Maint Features" -r vantiq-issues -al enhancement -el wontfix duplicate automated Verified -m $VI_MAINT -tc "#c6e0b4" -d \
-sn $CUR_RELEASE" Milestone Bugs" -r iqtools -al -el enhancement wontfix duplicate automated verified  -m $LATEST -tc "#f4b084" -d \
-sn $LAST_RELEASE" Maint Bugs" -r iqtools -al -el enhancement wontfix duplicate automated verified  -m $MAINT -tc "#f4b084" -d \
-sn "VI "$CUR_RELEASE" Milestone Bugs" -r vantiq-issues -al -el enhancement wontfix duplicate automated Verified -m $VI_LATEST -tc "#f4b084" -d \
-sn "VI "$LAST_RELEASE" Maint Bugs" -r vantiq-issues -al -el enhancement wontfix duplicate automated Verified -m $VI_MAINT -tc "#f4b084" -d