from fastapi import BackgroundTasks
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import EmailStr
from app.core.config import settings
from typing import List

# Email configuration
mail_conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=settings.MAIL_USE_CREDENTIALS,
    VALIDATE_CERTS=settings.MAIL_VALIDATE_CERTS
)

async def send_email_async(
    subject: str,
    recipients: List[EmailStr],
    body: str,
    background_tasks: BackgroundTasks
):
    """Send an email asynchronously"""
    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=body,
        subtype=MessageType.html
    )
    
    fm = FastMail(mail_conf)
    
    # Send email in the background
    background_tasks.add_task(
        fm.send_message, message
    )

async def send_password_reset_email(
    email: EmailStr, 
    token: str,
    background_tasks: BackgroundTasks
):
    """Send password reset email with token"""
    subject = "Password Reset Code - Your Account"
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e1e1e1; border-radius: 5px;">
        <div style="background-color: #4a86e8; padding: 15px; border-radius: 5px 5px 0 0;">
            <h2 style="color: white; margin: 0; text-align: center;">Password Reset</h2>
        </div>
        <div style="padding: 20px; background-color: #f9f9f9;">
            <p style="font-size: 16px; line-height: 1.5; color: #333;">Hello,</p>
            <p style="font-size: 16px; line-height: 1.5; color: #333;">You have requested to reset your password. Please use the code below to reset your password:</p>
            
            <div style="background-color: #e9e9e9; padding: 15px; margin: 20px 0; border-radius: 5px; text-align: center;">
                <code style="font-size: 20px; font-weight: bold; letter-spacing: 1px; color: #4a86e8;">{token}</code>
            </div>
            
            <p style="font-size: 16px; line-height: 1.5; color: #333;">If you did not request a password reset, please ignore this email.</p>
            <p style="font-size: 14px; color: #777;">This code will expire in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.</p>
        </div>
        <div style="padding: 15px; text-align: center; font-size: 12px; color: #888; background-color: #f1f1f1; border-radius: 0 0 5px 5px;">
            <p>This is an automated message, please do not reply to this email.</p>
            <p>&copy; {settings.API_TITLE} {settings.API_VERSION}</p>
        </div>
    </body>
    </html>
    """
    
    await send_email_async(
        subject=subject,
        recipients=[email],
        body=body,
        background_tasks=background_tasks
    ) 