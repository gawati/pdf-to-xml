pipeline {
    agent any

    environment { 
        // CI="false"
        DLD="/var/www/html/dl.gawati.org/dev"
        PKF="pdf-to-xml"
    } 

    stages {
        stage('Prerun Diag') {
            steps {
                sh 'pwd'
            }
        }
        stage('Setup') {
            steps {
                sh 'echo Setup'
            }
        }
        stage('Build') {
            steps {
                sh 'python lc_setup.py install --user'
                sh 'VERSION="`grep -i ^version: ${HOME}/.local/lib/python2.7/site-packages/pdfminer-20140328-py2.7.egg-info | cut -d " " -f 2`" ; echo "{ \"version\" : \"${VERSION}\" }" >package.json'
            }
        }
        stage('Upload') {
            steps {
                script {
                    def packageFile = readJSON file: 'package.json'
                    sh "cd build ; tar -cvjf $DLD/$PKF-${packageFile.version}.tbz ."
                    sh "cd build ; zip -r - . > $DLD/$PKF-${packageFile.version}.zip"
                    sh "[ -L $DLD/$PKF-latest.zip ] && rm -f $DLD/$PKF-latest.zip ; exit 0"
                    sh "[ -e $DLD/$PKF-latest.zip ] || ln -s $PKF-${packageFile.version}.zip $DLD/$PKF-latest.zip"
                    sh "[ -L $DLD/$PKF-latest.tbz ] && rm -f $DLD/$PKF-latest.tbz ; exit 0"
                    sh "[ -e $DLD/$PKF-latest.tbz ] || ln -s $PKF-${packageFile.version}.tbz $DLD/$PKF-latest.tbz"
                }
            }
        }
        stage('Clean') {
            steps {
                cleanWs(cleanWhenAborted: true, cleanWhenNotBuilt: true, cleanWhenSuccess: true, cleanWhenUnstable: true, cleanupMatrixParent: true, deleteDirs: true)
            }
        }        
    }
}
