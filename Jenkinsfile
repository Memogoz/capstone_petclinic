pipeline {
    agent any

    environment {
        GIT_COMMIT_SHORT = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        // === Merge Request (MR) or Pull Request (PR) ===
        stage('Static code analysis') {
            when {
                expression { return env.CHANGE_ID != null }
            }
            steps {
                sh './mvnw checkstyle:checkstyle'
            }
            post {
                always {
                    archiveArtifacts artifacts: 'target/checkstyle-result.xml', fingerprint: true
                }
            }
        }

        // === Merge Request (MR) or Pull Request (PR) ===
        stage('Test') {
            when {
                expression { return env.CHANGE_ID != null }
            }
            steps {
                sh './mvnw test'
            }
        }

        // === Merge Request (MR) or Pull Request (PR) and Main Branch ===
        stage('Build artifact') {
            when {
                expression { return env.CHANGE_ID != null }
            }
            steps {
                sh './mvnw package -DskipTests'
            }
        }

        // === Merge Request (MR) or Pull Request (PR) and Main Branch ===
        stage('Build & Push Docker Image') { // build and push docker image
            steps {
                script {
                    def isMR = env.CHANGE_ID != null

                    // Define repo and tag based on context
                    def repo = isMR ? "ggonzalezx/mr" : "ggonzalezx/main"

                    def tag = isMR ? "${GIT_COMMIT_SHORT}" : "latest"

                    def fullImageName = "${repo}:${tag}"

                    echo "Building Docker image with Dockerfile: ${fullImageName}"

                    // Build using Dockerfile
                    docker.build(fullImageName, "-f Dockerfile .")

                    // Authenticate and push to Docker Hub
                    docker.withRegistry('https://index.docker.io/v1/', 'dockerhub-token') {
                        docker.image(fullImageName).push()
                    }

                    echo "Docker image pushed to: https://hub.docker.com/repository/docker/${repo}"
                }
            }
        }
    }

    post {
        success {
            echo "Pipeline SUCCESS for ${env.BRANCH_NAME} (${env.CHANGE_ID ?: 'not an MR'})"
        }
        failure {
            echo "Pipeline FAILURE for ${env.BRANCH_NAME} (${env.CHANGE_ID ?: 'not an MR'})"
        }
    }
}
