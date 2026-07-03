import boto3

from app.config import settings

_resource = boto3.resource("dynamodb", region_name=settings.aws_region)

users_table = _resource.Table(settings.users_table)
identities_table = _resource.Table(settings.identities_table)
puzzles_table = _resource.Table(settings.puzzles_table)
scores_table = _resource.Table(settings.scores_table)
friendships_table = _resource.Table(settings.friendships_table)
friend_requests_table = _resource.Table(settings.friend_requests_table)
verification_codes_table = _resource.Table(settings.verification_codes_table)
password_reset_codes_table = _resource.Table(settings.password_reset_codes_table)
achievements_table = _resource.Table(settings.achievements_table)
