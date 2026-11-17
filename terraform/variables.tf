variable "aws_region" {
  description = "Target AWS deployment region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name identifier"
  type        = string
  default     = "sentiment-mlops"
}

variable "environment" {
  description = "Target deployment environment (dev, staging, production)"
  type        = string
  default     = "production"
}

variable "owner" {
  description = "Lead engineer / owner tag"
  type        = string
  default     = "Zeenat Riaz"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "node_instance_type" {
  description = "EC2 instance type for EKS inference nodes"
  type        = string
  default     = "t3.xlarge"
}

variable "desired_nodes" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 2
}

variable "min_nodes" {
  description = "Minimum number of worker nodes for autoscaling"
  type        = number
  default     = 1
}

variable "max_nodes" {
  description = "Maximum number of worker nodes for peak traffic"
  type        = number
  default     = 6
}
