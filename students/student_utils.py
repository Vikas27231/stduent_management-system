import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.contrib.auth.models import User
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StudentManager:
    def __init__(self):
        # Validate AWS settings
        self._validate_aws_settings()

        # Initialize AWS clients
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.dynamodb_client = boto3.client(
            'dynamodb',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.sns = boto3.client(
            'sns',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )

        # Initialize DynamoDB tables
        self.students_table = self.dynamodb.Table(settings.AWS_DYNAMODB_TABLE)
        self.courses_table = self.dynamodb.Table('Courses')

        # Ensure the Courses table exists and seed default courses
        self.ensure_courses_table()
        self.seed_courses()

    def _validate_aws_settings(self):
        """Validate required AWS settings."""
        required_settings = {
            'AWS_ACCESS_KEY_ID': settings.AWS_ACCESS_KEY_ID,
            'AWS_SECRET_ACCESS_KEY': settings.AWS_SECRET_ACCESS_KEY,
            'AWS_REGION': settings.AWS_REGION,
            'AWS_DYNAMODB_TABLE': settings.AWS_DYNAMODB_TABLE,
            'AWS_S3_BUCKET_NAME': settings.AWS_S3_BUCKET_NAME,
        }
        for key, value in required_settings.items():
            if not value:
                raise ValueError(f"Missing required AWS setting: {key}")
        # AWS_SNS_TOPIC_ARN is optional; we'll check it before using SNS
        logger.info("AWS settings validated successfully.")

    def ensure_courses_table(self):
        """Ensure the Courses table exists in DynamoDB."""
        try:
            self.dynamodb_client.describe_table(TableName='Courses')
            logger.info("Courses table already exists.")
        except self.dynamodb_client.exceptions.ResourceNotFoundException:
            try:
                self.dynamodb_client.create_table(
                    TableName='Courses',
                    KeySchema=[{'AttributeName': 'name', 'KeyType': 'HASH'}],
                    AttributeDefinitions=[{'AttributeName': 'name', 'AttributeType': 'S'}],
                    BillingMode='PAY_PER_REQUEST'
                )
                self.dynamodb_client.get_waiter('table_exists').wait(TableName='Courses')
                logger.info("Courses table created successfully.")
            except ClientError as e:
                logger.error(f"Error creating Courses table: {str(e)}")
                raise

    def seed_courses(self):
        """Seed default courses into DynamoDB if none exist."""
        try:
            existing_courses = self.get_all_courses()
            if not existing_courses:
                default_courses = [
                    {'name': 'Master of Computer Application (MCA)', 'duration': '2 years'},
                    {'name': 'Bachelor of Computer Application (BCA)', 'duration': '3 years'},
                    {'name': 'BSc in Data Science', 'duration': '4 years'},
                ]
                for course in default_courses:
                    self.courses_table.put_item(Item=course)
                logger.info("Default courses seeded successfully.")
            else:
                logger.info(f"Found {len(existing_courses)} existing courses, skipping seeding.")
        except ClientError as e:
            logger.error(f"Error seeding courses: {str(e)}")
            raise

    def add_student(self, student_data, profile_picture=None, user=None):
        """Add a new student to DynamoDB and upload profile picture to S3."""
        try:
            if not user:
                logger.error("No user provided for adding student.")
                return False

            student_id = student_data.get('student_id')
            if not student_id:
                logger.error("Student ID is required.")
                return False

            profile_picture_url = ''
            if profile_picture:
                try:
                    s3_key = f"student-profiles/{student_id}/{profile_picture.name}"
                    self.s3.upload_fileobj(profile_picture, settings.AWS_S3_BUCKET_NAME, s3_key)
                    profile_picture_url = f"https://{settings.AWS_S3_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
                    logger.info(f"Profile picture uploaded to S3: {profile_picture_url}")
                except ClientError as e:
                    logger.error(f"Failed to upload profile picture to S3 for student {student_id}: {str(e)}")
                    raise

            item = {
                'student_id': student_id,
                'first_name': student_data.get('first_name', ''),
                'last_name': student_data.get('last_name', ''),
                'email': student_data.get('email', ''),
                'mobile_number': student_data.get('mobile_number', ''),
                'course': student_data.get('course', ''),
                'profile_picture': profile_picture_url,
                'user_id': str(user.id)  # Associate with the user
            }
            self.students_table.put_item(Item=item)

            # Send SNS notification for new student if configured
            if hasattr(settings, 'AWS_SNS_TOPIC_ARN') and settings.AWS_SNS_TOPIC_ARN:
                try:
                    self.sns.publish(
                        TopicArn=settings.AWS_SNS_TOPIC_ARN,
                        Message=f"New student added by {user.username}: {item['first_name']} {item['last_name']} (ID: {student_id})",
                        Subject="New Student Added"
                    )
                    logger.info(f"SNS notification sent for new student {student_id}.")
                except ClientError as e:
                    logger.error(f"Failed to send SNS notification for student {student_id}: {str(e)}")
                    # Continue even if SNS fails, as it's not critical to the operation

            logger.info(f"Student {student_id} added successfully by user {user.username}.")
            return True

        except ClientError as e:
            logger.error(f"Error adding student {student_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error adding student {student_id}: {str(e)}")
            return False

    def get_student(self, student_id, user=None):
        """Retrieve a student by student_id for the specified user."""
        try:
            response = self.students_table.get_item(Key={'student_id': student_id})
            student = response.get('Item')
            if not student:
                logger.warning(f"Student {student_id} not found.")
                return None
            # Check if the student belongs to the user
            if user and str(student.get('user_id', '')) != str(user.id):
                logger.warning(f"User {user.username} does not have access to student {student_id}.")
                return None
            return student
        except ClientError as e:
            logger.error(f"Error retrieving student {student_id}: {str(e)}")
            return None

    def get_all_students(self, user=None):
        """Retrieve all students for the specified user from DynamoDB."""
        try:
            response = self.students_table.scan()
            students = response.get('Items', [])
            if user:
                students = [s for s in students if str(s.get('user_id', '')) == str(user.id)]
            logger.info(f"Retrieved {len(students)} students for user {user.username if user else 'all users'}.")
            return students
        except ClientError as e:
            logger.error(f"Error scanning students: {str(e)}")
            return []

    def update_student(self, student_id, updated_data, profile_picture=None, user=None):
        """Update an existing student."""
        try:
            student = self.get_student(student_id, user)
            if not student:
                logger.warning(f"Student {student_id} not found or user {user.username if user else 'unknown'} does not have access.")
                return False

            profile_picture_url = student.get('profile_picture', '')
            if profile_picture:
                try:
                    s3_key = f"student-profiles/{student_id}/{profile_picture.name}"
                    self.s3.upload_fileobj(profile_picture, settings.AWS_S3_BUCKET_NAME, s3_key)
                    profile_picture_url = f"https://{settings.AWS_S3_BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
                    logger.info(f"Profile picture updated for student {student_id}: {profile_picture_url}")
                except ClientError as e:
                    logger.error(f"Failed to upload profile picture to S3 for student {student_id}: {str(e)}")
                    raise

            item = {
                'student_id': student_id,
                'first_name': updated_data.get('first_name', student['first_name']),
                'last_name': updated_data.get('last_name', student['last_name']),
                'email': updated_data.get('email', student['email']),
                'mobile_number': updated_data.get('mobile_number', student['mobile_number']),
                'course': updated_data.get('course', student['course']),
                'profile_picture': profile_picture_url,
                'user_id': student['user_id']  # Retain the original user_id
            }
            self.students_table.put_item(Item=item)
            logger.info(f"Student {student_id} updated successfully by user {user.username if user else 'unknown'}.")
            return True
        except ClientError as e:
            logger.error(f"Error updating student {student_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating student {student_id}: {str(e)}")
            return False

    def delete_student(self, student_id, user=None):
        """Delete a student from DynamoDB."""
        try:
            student = self.get_student(student_id, user)
            if not student:
                logger.warning(f"Student {student_id} not found or user {user.username if user else 'unknown'} does not have access.")
                return False

            self.students_table.delete_item(Key={'student_id': student_id})

            # Send SNS email notification for student deletion if configured
            if hasattr(settings, 'AWS_SNS_TOPIC_ARN') and settings.AWS_SNS_TOPIC_ARN:
                try:
                    self.sns.publish(
                        TopicArn=settings.AWS_SNS_TOPIC_ARN,
                        Message=f"Student deleted by {user.username if user else 'unknown'}: {student['first_name']} {student['last_name']} (Roll Number: {student_id})",
                        Subject="Student Deleted Notification"
                    )
                    logger.info(f"SNS notification sent for student deletion {student_id}.")
                except ClientError as e:
                    logger.error(f"Failed to send SNS notification for student deletion {student_id}: {str(e)}")
                    # Continue even if SNS fails

            logger.info(f"Student {student_id} deleted successfully by user {user.username if user else 'unknown'}.")
            return True
        except ClientError as e:
            logger.error(f"Error deleting student {student_id}: {str(e)}")
            return False

    def add_course(self, course_data):
        """Add a new course to DynamoDB."""
        try:
            course_name = course_data.get('name')
            if not course_name:
                logger.error("Course name is required.")
                return False

            existing_course = self.courses_table.get_item(Key={'name': course_name}).get('Item')
            if existing_course:
                logger.warning(f"Course {course_name} already exists.")
                return False

            item = {
                'name': course_name,
                'duration': course_data.get('duration', '')
            }
            self.courses_table.put_item(Item=item)
            logger.info(f"Course {course_name} added successfully.")
            return True
        except ClientError as e:
            logger.error(f"Error adding course: {str(e)}")
            return False

    def get_all_courses(self):
        """Retrieve all courses from DynamoDB."""
        try:
            response = self.courses_table.scan()
            courses = response.get('Items', [])
            logger.info(f"Retrieved {len(courses)} courses from DynamoDB.")
            return courses
        except ClientError as e:
            logger.error(f"Error scanning courses: {str(e)}")
            return []

    def update_course(self, course_id, updated_data):
        """Update an existing course."""
        try:
            course_name = updated_data.get('name')
            if not course_name:
                logger.error("Updated course name is required.")
                return False

            self.courses_table.delete_item(Key={'name': course_id})
            item = {
                'name': course_name,
                'duration': updated_data.get('duration', '')
            }
            self.courses_table.put_item(Item=item)
            logger.info(f"Course {course_id} updated successfully to {course_name}.")
            return True
        except ClientError as e:
            logger.error(f"Error updating course {course_id}: {str(e)}")
            return False