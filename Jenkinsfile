pipeline {
    agent any

    parameters {
        string(name: 'S3_BUCKET', defaultValue: 'default-terraform-state-bucket-871964', description: 'Enter the S3 bucket name')
        string(name: 'AWS_REGION', defaultValue: 'us-east-1', description: 'Enter the AWS region')
    }

    environment {
        GIT_COMMIT_SHORT = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
        ECR_REPO_URL = ''
        ECR_REPO_NAME = ''
        WEBSITE_URL  = ''
        APP_VERSION = ''
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

        // === Main Branch ===
        stage('Tag and push git version') {
            when {
                expression { return env.CHANGE_ID == null }
            }
            steps {
                script {
                    // fetch tags (if not already present)
                    sh 'git fetch --tags'

                    // Save next version into environment variable
                    def nextVersion = sh(script: 'python3 get_next_version.py', returnStdout: true).trim()
                    env.APP_VERSION = nextVersion

                    // Tag the Git repo and push
                    sh """
                        git tag ${env.APP_VERSION}
                        git push origin ${env.APP_VERSION}
                    """
                }
            }
        }

        stage('Get ECR repo url and ALB url') {
            steps {
                script {
                    // Download the state file from S3
                    sh "aws s3 cp s3://${params.S3_BUCKET}/infrastructure/terraform.tfstate ./terraform.tfstate --region ${params.AWS_REGION}"

                    // Extract outputs using jq
                    def ecrRepoFullUrl = sh(script: "jq -r '.outputs.ecr_repo_url.value' ./terraform.tfstate", returnStdout: true).trim()
                    // sample output: 123456789012.dkr.ecr.us-east-1.amazonaws.com/docker-images-repo
                    def ecrRepoUrl = ecrRepoFullUrl.split('/')[0]
                    def ecrRepoName = ecrRepoFullUrl.split('/')[1]
                    def websiteUrl = sh(script: "jq -r '.outputs.website_url.value' ./terraform.tfstate", returnStdout: true).trim()

                    // Set environment variables
                    env.ECR_REPO_URL = ecrRepoUrl
                    env.ECR_REPO_NAME = ecrRepoName
                    env.WEBSITE_URL = websiteUrl

                    // Print the values
                    echo "ECR_REPO_URL = ${env.ECR_REPO_URL}"
                    echo "ECR_REPO_NAME = ${env.ECR_REPO_NAME}"
                    echo "WEBSITE_URL = ${env.WEBSITE_URL}"
                }
            }
        }

        // === Merge Request (MR) or Pull Request (PR) and Main Branch ===
        stage('Build & Push Docker Image') { // build and push docker image
            steps {
                script {
                    def isMR = env.CHANGE_ID != null
                    def awsCredentialId = 'aws-credentials' // Jenkins AWS credential ID

                    //def ecrRegistry = env.ECR_REPO_URL
                    //def repoName = env.ECR_REPO_NAME

                    // Determine image tag: commit SHA for merge requests, or APP_VERSION otherwise
                    def tag = isMR ? "${GIT_COMMIT_SHORT}" : env.APP_VERSION

                    def fullImageName = "${env.ECR_REPO_URL}/${env.ECR_REPO_NAME}:${tag}"

                    echo "Building Docker image: ${fullImageName}"

                    // Build Docker image using Dockerfile in the project root
                    docker.build(fullImageName)

                    // Authenticate with ECR and push the image
                    docker.withRegistry("https://${env.ECR_REPO_URL}", awsCredentialId) {
                        docker.image(fullImageName).push()
                    }

                    echo "Docker image pushed to ECR: ${fullImageName}"
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
