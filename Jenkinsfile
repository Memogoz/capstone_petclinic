pipeline {
    agent any

    parameters {
        string(name: 'S3_BUCKET', defaultValue: 'default-terraform-state-bucket-871964', description: 'Enter the S3 bucket name')
        string(name: 'AWS_REGION', defaultValue: 'us-east-1', description: 'Enter the AWS region')
    }

    environment {
        GIT_COMMIT_SHORT = sh(script: "git rev-parse --short HEAD", returnStdout: true).trim()
        ECR_URL = ''
        ECR_REPO_NAME = ''
        WEBSITE_URL  = ''
        APP_VERSION = ''
        POSTGRES_HOST = ''
        POSTGRES_PORT = ''
        POSTGRES_USER = ''
        POSTGRES_PASSWORD = ''
        POSTGRES_DB = ''
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
                sh './mvnw test -Dcheckstyle.skip=true'
            }
        }

        // === Merge Request (MR) or Pull Request (PR) and Normal Commit ===
        stage('Build artifact') {
            when {
                expression { return env.CHANGE_ID != null }
            }
            steps {
                sh './mvnw package -DskipTests -Dcheckstyle.skip=true'
            }
        }

        // === Main Branch ===
        stage('Tag and push git version') {
            when {
                branch 'main'
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

        // === Merge Request (MR) or Pull Request (PR) and Normal Commit ===
        stage('Get ECR repo url, ALB url and Postgress variables') {
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

                    def postgresHost = sh(script: "jq -r '.outputs.postgres_host.value' ./terraform.tfstate", returnStdout: true).trim()
                    def postgresPort = sh(script: "jq -r '.outputs.postgres_port.value' ./terraform.tfstate", returnStdout: true).trim()
                    def postgresUser = sh(script: "jq -r '.outputs.postgres_user.value' ./terraform.tfstate", returnStdout: true).trim()
                    def postgresPassword = sh(script: "jq -r '.outputs.postgres_password.value' ./terraform.tfstate", returnStdout: true).trim()
                    def postgresDb = sh(script: "jq -r '.outputs.postgres_db.value' ./terraform.tfstate", returnStdout: true).trim()



                    // Set environment variables
                    env.ECR_URL = ecrRepoUrl
                    env.ECR_REPO_NAME = ecrRepoName

                    env.WEBSITE_URL = websiteUrl

                    env.POSTGRES_HOST = postgresHost
                    env.POSTGRES_PORT = postgresPort
                    env.POSTGRES_USER = postgresUser
                    env.POSTGRES_PASSWORD = postgresPassword
                    env.POSTGRES_DB = postgresDb


                    // Print the values
                    echo "ECR_URL = ${env.ECR_URL}"
                    echo "ECR_REPO_NAME = ${env.ECR_REPO_NAME}"
                    echo "WEBSITE_URL = ${env.WEBSITE_URL}"
                }
            }
        }

        // === Merge Request (MR) or Pull Request (PR) and Normal Commit ===
        stage('Build & Push Docker Image') {
            steps {
                script {

                    def isMR = env.CHANGE_ID != null

                    // Determine image tag: commit SHA for merge requests, or APP_VERSION otherwise
                    def tag = isMR ? "${GIT_COMMIT_SHORT}" : env.APP_VERSION

                    def fullImageName = "${env.ECR_URL}/${env.ECR_REPO_NAME}:${tag}"

                    echo "Building Docker image: ${fullImageName}"

                    // Build Docker image using Dockerfile in the project root
                    docker.build(fullImageName)

                    // Authenticate with ECR and push the image
                    // Example autenticate from cli:     aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <aws-account-id>.dkr.ecr.<region>.amazonaws.com
                    docker.withRegistry("https://${env.ECR_URL}") {
                        docker.image(fullImageName).push()
                    }

                    echo "Docker image pushed to ECR: ${fullImageName}"
                }
            }
        }

        // === Main Branch ===
        stage('Wait for deploy Approval') {
            when {
                branch 'main'
                expression { return env.CHANGE_ID == null }
            }
            steps {
                echo 'Waiting for deploy approval...'
                input message: "Deploy new version?"
            }
        }

        // === Main Branch ===
        stage('Deploy with Ansible') {
            when {
                branch 'main' 
                expression { return env.CHANGE_ID == null }
            }
            steps {
                script {
                    def region = params.AWS_REGION
                    sh """
                        echo "Fetching Bastion IP..."
                        BASTION_IP=\$(aws ec2 describe-instances \
                            --region ${region} \
                            --filters "Name=tag:Role,Values=bastion" "Name=instance-state-name,Values=running" \
                            --query "Reservations[].Instances[].PublicIpAddress" \
                            --output text)

                        echo "Running Ansible playbook using bastion at \$BASTION_IP"

                        export ANSIBLE_CONFIG=./Ansible/ansible.cfg

                        ~/venv/bin/ansible-playbook \
                            -i ./Ansible/inventory.aws_ec2.yaml \
                            ./Ansible/deploy-petclinic.yaml \
                            --ssh-common-args="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ProxyCommand='ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i ~/.aws-keys/jenkins-worker-key -W %h:%p -q ubuntu@\$BASTION_IP'" \
                            --private-key=~/.aws-keys/web-instances-key || true
                    """
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