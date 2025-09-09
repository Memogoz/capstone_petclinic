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
                    sh 'git fetch --tags'

                    APP_VERSION = sh(script: '~/venv/bin/python3 get_next_version.py', returnStdout: true).trim()
                    echo "Next version: ${APP_VERSION}"

                    withEnv(["APP_VERSION=${APP_VERSION}"]) {
                        sh """
                            git tag $APP_VERSION
                            git push origin $APP_VERSION
                        """
                    }
                }
            }
        }

        // === Merge Request (MR) or Pull Request (PR) and Normal Commit ===
        stage('Get ECR repo url, ALB url and Postgress variables') {
            steps {
                script {
                    sh "aws s3 cp s3://${params.S3_BUCKET}/infrastructure/terraform.tfstate ./terraform.tfstate --region ${params.AWS_REGION}"

                    def ecrRepoFullUrl = sh(script: "jq -r '.outputs.ecr_repo_url.value' ./terraform.tfstate", returnStdout: true).trim()
                    ECR_URL = ecrRepoFullUrl.split('/')[0]
                    ECR_REPO_NAME = ecrRepoFullUrl.split('/')[1]

                    WEBSITE_URL     = sh(script: "jq -r '.outputs.website_url.value' ./terraform.tfstate", returnStdout: true).trim()
                    POSTGRES_HOST   = sh(script: "jq -r '.outputs.postgres_host.value' ./terraform.tfstate", returnStdout: true).trim()
                    POSTGRES_PORT   = sh(script: "jq -r '.outputs.postgres_port.value' ./terraform.tfstate", returnStdout: true).trim()
                    POSTGRES_USER   = sh(script: "jq -r '.outputs.postgres_user.value' ./terraform.tfstate", returnStdout: true).trim()
                    POSTGRES_PASSWORD = sh(script: "jq -r '.outputs.postgres_password.value' ./terraform.tfstate", returnStdout: true).trim()
                    POSTGRES_DB     = sh(script: "jq -r '.outputs.postgres_db.value' ./terraform.tfstate", returnStdout: true).trim()

                    echo "ECR_URL = ${ECR_URL}"
                    echo "ECR_REPO_NAME = ${ECR_REPO_NAME}"
                    echo "WEBSITE_URL = ${WEBSITE_URL}"
                }
            }
        }

        // === Merge Request (MR) or Pull Request (PR) and Normal Commit ===
        stage('Build & Push Docker Image') {
            steps {
                script {
                    def isMR = env.CHANGE_ID != null

                    // Use APP_VERSION (should also be a top-level Groovy variable)
                    def tag = isMR ? "${GIT_COMMIT_SHORT}" : APP_VERSION

                    // Use top-level Groovy vars here — not env.ECR_URL / env.ECR_REPO_NAME
                    def fullImageName = "${ECR_URL}/${ECR_REPO_NAME}:${tag}"

                    echo "Building Docker image: ${fullImageName}"

                    // Build Docker image
                    docker.build(fullImageName)

                    // Push to ECR
                    docker.withRegistry("https://${ECR_URL}") {
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