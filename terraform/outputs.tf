output "cluster_name" {
  description = "The name of the provisioned EKS cluster"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS API server endpoint URL"
  value       = module.eks.cluster_endpoint
}

output "ecr_repository_url" {
  description = "ECR repository URL for model serving container images"
  value       = aws_ecr_repository.api_repo.repository_url
}

output "vpc_id" {
  description = "ID of the VPC created for inference workloads"
  value       = module.vpc.vpc_id
}
