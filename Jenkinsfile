pipeline {
    agent any
    options {
        disableConcurrentBuilds()
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }
    parameters {
        choice(name: 'TEST_MODE', choices: ['API_ONLY', 'FULL'], description: 'FULL adds Android UI demo tests, without backend integration.')
    }
    environment { CI_OUTPUT = "artifacts/ci/${JOB_BASE_NAME}-${BUILD_NUMBER}" }
    stages {
        stage('Python environment') {
            steps {
                sh 'python3 -m venv .venv'
                script {
                    def requirements = params.TEST_MODE == 'FULL' ? 'requirements-ui.txt' : 'requirements.txt'
                    sh ".venv/bin/python -m pip install -r ${requirements}"
                }
                sh '.venv/bin/python scripts/ci_runner.py prepare --output "$CI_OUTPUT"'
            }
        }
        stage('API and storage') {
            steps { sh '.venv/bin/python scripts/ci_runner.py api --output "$CI_OUTPUT"' }
        }
        stage('Android UI demo') {
            when { expression { params.TEST_MODE == 'FULL' } }
            steps { sh '.venv/bin/python scripts/ci_runner.py ui --output "$CI_OUTPUT"' }
        }
    }
    post {
        always {
            script {
                def cleanupCode = sh(returnStatus: true, script: '.venv/bin/python scripts/ci_runner.py cleanup --output "$CI_OUTPUT"')
                def reportCode = sh(returnStatus: true, script: '.venv/bin/python scripts/ci_runner.py report --output "$CI_OUTPUT"')
                def publishingFailed = false
                def suites = params.TEST_MODE == 'FULL' ? ['api', 'ui'] : ['api']
                for (suite in suites) {
                    try {
                        junit(testResults: "${env.CI_OUTPUT}/${suite}/junit.xml", allowEmptyResults: false)
                    } catch (Exception problem) {
                        echo "JUnit ${suite} publication failed: ${problem.message}"
                        publishingFailed = true
                    }
                }
                try {
                    archiveArtifacts(artifacts: "${env.CI_OUTPUT}/**", allowEmptyArchive: false)
                } catch (Exception problem) {
                    echo "Archive failed: ${problem.message}"
                    publishingFailed = true
                }
                if (cleanupCode != 0 || reportCode != 0 || publishingFailed) {
                    error('Post-processing failed; inspect retained evidence.')
                }
            }
        }
        success { echo 'Completed. Android results validate UI demo behavior only.' }
        failure { echo 'Failed; inspect actual stages and retained artifacts.' }
    }
}
