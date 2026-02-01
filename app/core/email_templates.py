"""
Email Templates for UmukoziHR Resume Tailor
Psychology-driven, high-converting email templates

Design Principles:
- Clean, professional design with UmukoziHR branding
- Mobile-responsive (single column, large CTAs)
- Clear hierarchy with one primary CTA per email
- Psychology-driven copy (urgency, social proof, loss aversion)
"""

import os
from typing import List, Tuple

APP_URL = os.getenv("APP_URL", "https://tailor.umukozihr.com")


def _base_template(content: str, include_unsubscribe: bool = True) -> str:
    """Base HTML email template with UmukoziHR branding"""
    unsubscribe_section = ""
    if include_unsubscribe:
        unsubscribe_section = """
        <tr>
          <td style="padding: 20px 30px; text-align: center; border-top: 1px solid #e5e5e5;">
            <p style="margin: 0; font-size: 12px; color: #9ca3af;">
              You received this email because you signed up for UmukoziHR Resume Tailor.<br>
              <a href="{unsubscribe_url}" style="color: #9ca3af; text-decoration: underline;">Unsubscribe</a> from these emails
            </p>
          </td>
        </tr>
        """
    
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>UmukoziHR</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f3f4f6;">
    <tr>
      <td align="center" style="padding: 40px 20px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 600px; background-color: #ffffff; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
          <!-- Header -->
          <tr>
            <td style="padding: 30px 30px 20px; text-align: center; background: linear-gradient(135deg, #f97316 0%, #ea580c 100%); border-radius: 16px 16px 0 0;">
              <h1 style="margin: 0; font-size: 28px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">UmukoziHR</h1>
              <p style="margin: 8px 0 0; font-size: 14px; color: rgba(255,255,255,0.9);">Resume Tailor</p>
            </td>
          </tr>
          
          <!-- Content -->
          {content}
          
          <!-- Footer -->
          <tr>
            <td style="padding: 20px 30px; text-align: center; background-color: #fafafa; border-radius: 0 0 16px 16px;">
              <p style="margin: 0 0 10px; font-size: 12px; color: #6b7280;">
                Made with care in Africa for job seekers worldwide
              </p>
              <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                <a href="{APP_URL}" style="color: #f97316; text-decoration: none;">tailor.umukozihr.com</a>
              </p>
            </td>
          </tr>
          
          {unsubscribe_section}
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _cta_button(text: str, url: str, color: str = "#f97316") -> str:
    """Generate a CTA button"""
    return f"""
    <a href="{url}" style="display: inline-block; padding: 16px 32px; background-color: {color}; color: #ffffff; font-size: 16px; font-weight: 600; text-decoration: none; border-radius: 12px; box-shadow: 0 4px 14px 0 rgba(249, 115, 22, 0.39);">
      {text}
    </a>
    """


# =============================================================================
# EMAIL TEMPLATES
# =============================================================================

def get_welcome_email(name: str) -> Tuple[str, str]:
    """Welcome email - sent immediately after signup"""
    subject = f"Welcome to UmukoziHR, {name}! Let's land your dream job"
    
    content = f"""
    <tr>
      <td style="padding: 30px;">
        <h2 style="margin: 0 0 20px; font-size: 24px; color: #1f2937;">Hey {name}!</h2>
        
        <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          Welcome to <strong>UmukoziHR Resume Tailor</strong> - your AI-powered career companion. You've just taken the first step toward landing your dream job.
        </p>
        
        <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 12px; padding: 20px; margin: 20px 0;">
          <p style="margin: 0; font-size: 15px; color: #92400e;">
            <strong>Did you know?</strong> Tailored resumes are 6x more likely to get interviews. That's exactly what we help you do - automatically.
          </p>
        </div>
        
        <p style="margin: 0 0 25px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          Here's what you can do now:
        </p>
        
        <ul style="margin: 0 0 25px; padding-left: 20px; font-size: 15px; line-height: 1.8; color: #4b5563;">
          <li><strong>Complete your profile</strong> - Add your experience, skills, and education</li>
          <li><strong>Paste a job description</strong> - Any job you're interested in</li>
          <li><strong>Get tailored documents</strong> - Resume + cover letter in seconds</li>
        </ul>
        
        <div style="text-align: center; margin: 30px 0;">
          {_cta_button("Complete Your Profile", f"{APP_URL}/onboarding")}
        </div>
        
        <p style="margin: 0; font-size: 14px; color: #6b7280; text-align: center;">
          Your career upgrade starts now.
        </p>
      </td>
    </tr>
    """
    
    return subject, _base_template(content)


def get_onboarding_nudge_email(name: str, completeness: int) -> Tuple[str, str]:
    """Onboarding nudge - sent 24h after signup if incomplete"""
    subject = f"{name}, your profile is {completeness}% ready - let's finish it"
    
    progress_bar = f"""
    <div style="background-color: #e5e7eb; border-radius: 10px; height: 12px; margin: 15px 0; overflow: hidden;">
      <div style="background: linear-gradient(90deg, #f97316 0%, #ea580c 100%); height: 100%; width: {completeness}%; border-radius: 10px;"></div>
    </div>
    """
    
    content = f"""
    <tr>
      <td style="padding: 30px;">
        <h2 style="margin: 0 0 20px; font-size: 24px; color: #1f2937;">Don't lose your progress, {name}</h2>
        
        <p style="margin: 0 0 15px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          You started something great on UmukoziHR. Your profile is <strong>{completeness}% complete</strong>.
        </p>
        
        {progress_bar}
        
        <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 15px; margin: 20px 0; border-radius: 0 8px 8px 0;">
          <p style="margin: 0; font-size: 14px; color: #991b1b;">
            <strong>The job market moves fast.</strong> Every day you wait is an opportunity missed. Complete your profile now and start applying.
          </p>
        </div>
        
        <p style="margin: 0 0 25px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          It only takes <strong>5 more minutes</strong> to finish. Then you'll have:
        </p>
        
        <ul style="margin: 0 0 25px; padding-left: 20px; font-size: 15px; line-height: 1.8; color: #4b5563;">
          <li>AI-tailored resumes for any job</li>
          <li>Custom cover letters that stand out</li>
          <li>Both PDF and Word formats</li>
        </ul>
        
        <div style="text-align: center; margin: 30px 0;">
          {_cta_button("Finish My Profile", f"{APP_URL}/onboarding")}
        </div>
      </td>
    </tr>
    """
    
    return subject, _base_template(content)


def get_first_generation_email(name: str, company: str, title: str) -> Tuple[str, str]:
    """First generation celebration - sent after first resume generation"""
    subject = f"Your first tailored resume is ready, {name}!"
    
    content = f"""
    <tr>
      <td style="padding: 30px;">
        <div style="text-align: center; margin-bottom: 20px;">
          <span style="font-size: 48px;">🎉</span>
        </div>
        
        <h2 style="margin: 0 0 20px; font-size: 24px; color: #1f2937; text-align: center;">Congratulations, {name}!</h2>
        
        <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #4b5563; text-align: center;">
          You just generated your first tailored resume for <strong>{title}</strong> at <strong>{company}</strong>. That's a big step!
        </p>
        
        <div style="background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); border-radius: 12px; padding: 20px; margin: 20px 0; text-align: center;">
          <p style="margin: 0; font-size: 15px; color: #065f46;">
            <strong>Pro tip:</strong> Apply to 3-5 jobs per week with tailored resumes. Users who do this land interviews 40% faster.
          </p>
        </div>
        
        <p style="margin: 0 0 25px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          Your documents are waiting in your dashboard. Remember, you can:
        </p>
        
        <ul style="margin: 0 0 25px; padding-left: 20px; font-size: 15px; line-height: 1.8; color: #4b5563;">
          <li>Download PDF for online applications</li>
          <li>Download Word to make quick edits</li>
          <li>Generate more tailored resumes - no limits!</li>
        </ul>
        
        <div style="text-align: center; margin: 30px 0;">
          {_cta_button("View My Resume", f"{APP_URL}/app")}
        </div>
        
        <p style="margin: 0; font-size: 14px; color: #6b7280; text-align: center;">
          Keep the momentum going. Your next interview could be one resume away.
        </p>
      </td>
    </tr>
    """
    
    return subject, _base_template(content)


def get_inactivity_48h_email(name: str, completeness: int) -> Tuple[str, str]:
    """48-hour inactivity nudge - urgency and FOMO"""
    subject = f"Your resume is waiting for you, {name}"
    
    content = f"""
    <tr>
      <td style="padding: 30px;">
        <h2 style="margin: 0 0 20px; font-size: 24px; color: #1f2937;">Hey {name},</h2>
        
        <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          We noticed you haven't been back in a couple of days. Your profile is <strong>{completeness}% complete</strong> and ready to work for you.
        </p>
        
        <div style="background-color: #fef3c7; border-radius: 12px; padding: 20px; margin: 20px 0;">
          <p style="margin: 0; font-size: 15px; color: #92400e;">
            <strong>While you were away:</strong> Hundreds of new jobs were posted. Don't let your dream role slip away because your resume wasn't ready.
          </p>
        </div>
        
        <p style="margin: 0 0 25px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          The job market moves fast. Your next opportunity could be posted right now. Let's get your resume ready.
        </p>
        
        <div style="text-align: center; margin: 30px 0;">
          {_cta_button("Continue Building", f"{APP_URL}/app")}
        </div>
        
        <p style="margin: 0; font-size: 14px; color: #6b7280; text-align: center; font-style: italic;">
          Jobs don't wait. Neither should you.
        </p>
      </td>
    </tr>
    """
    
    return subject, _base_template(content)


def get_winback_7day_email(name: str, generations: int) -> Tuple[str, str]:
    """7-day win-back email - re-engagement with value reminder"""
    subject = f"We miss you, {name} - your career goals are waiting"
    
    content = f"""
    <tr>
      <td style="padding: 30px;">
        <h2 style="margin: 0 0 20px; font-size: 24px; color: #1f2937;">It's been a while, {name}</h2>
        
        <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          A week has passed since you last used UmukoziHR. We hope your job search is going well!
        </p>
        
        {"<p style='margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #4b5563;'>You've generated <strong>" + str(generations) + " tailored resume(s)</strong> so far. That's great progress!</p>" if generations > 0 else ""}
        
        <div style="background: linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%); border-radius: 12px; padding: 20px; margin: 20px 0;">
          <p style="margin: 0 0 10px; font-size: 16px; font-weight: 600; color: #5b21b6;">What's new at UmukoziHR?</p>
          <ul style="margin: 0; padding-left: 20px; font-size: 14px; color: #6b21a8; line-height: 1.8;">
            <li>New achievement badges to unlock</li>
            <li>Track your interview and offer progress</li>
            <li>Share your wins on LinkedIn</li>
          </ul>
        </div>
        
        <p style="margin: 0 0 25px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          Whether you're still searching or just keeping your options open, we're here to help you put your best foot forward.
        </p>
        
        <div style="text-align: center; margin: 30px 0;">
          {_cta_button("Get Back to Job Hunting", f"{APP_URL}/app")}
        </div>
        
        <p style="margin: 0; font-size: 14px; color: #6b7280; text-align: center;">
          Your next opportunity is out there. Let's find it together.
        </p>
      </td>
    </tr>
    """
    
    return subject, _base_template(content)


def get_weekly_digest_email(
    name: str, 
    generations_this_week: int, 
    streak: int, 
    xp: int,
    new_achievements: List[str]
) -> Tuple[str, str]:
    """Weekly digest - progress recap and motivation"""
    subject = f"Your weekly job hunt recap, {name}"
    
    achievements_section = ""
    if new_achievements:
        badges = "".join([f"<span style='display: inline-block; background-color: #fef3c7; color: #92400e; padding: 4px 12px; border-radius: 20px; font-size: 13px; margin: 4px;'>{a}</span>" for a in new_achievements])
        achievements_section = f"""
        <div style="background-color: #fef3c7; border-radius: 12px; padding: 20px; margin: 20px 0;">
          <p style="margin: 0 0 10px; font-size: 14px; font-weight: 600; color: #92400e;">New Achievements Unlocked!</p>
          <div>{badges}</div>
        </div>
        """
    
    content = f"""
    <tr>
      <td style="padding: 30px;">
        <h2 style="margin: 0 0 20px; font-size: 24px; color: #1f2937;">Your Weekly Recap</h2>
        
        <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          Hey {name}, here's how your job hunt went this week:
        </p>
        
        <!-- Stats Grid -->
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin: 20px 0;">
          <tr>
            <td width="33%" style="text-align: center; padding: 15px;">
              <div style="background-color: #f3f4f6; border-radius: 12px; padding: 20px;">
                <p style="margin: 0; font-size: 32px; font-weight: 700; color: #f97316;">{generations_this_week}</p>
                <p style="margin: 5px 0 0; font-size: 12px; color: #6b7280;">Resumes Generated</p>
              </div>
            </td>
            <td width="33%" style="text-align: center; padding: 15px;">
              <div style="background-color: #f3f4f6; border-radius: 12px; padding: 20px;">
                <p style="margin: 0; font-size: 32px; font-weight: 700; color: #10b981;">{streak}</p>
                <p style="margin: 5px 0 0; font-size: 12px; color: #6b7280;">Day Streak</p>
              </div>
            </td>
            <td width="33%" style="text-align: center; padding: 15px;">
              <div style="background-color: #f3f4f6; border-radius: 12px; padding: 20px;">
                <p style="margin: 0; font-size: 32px; font-weight: 700; color: #8b5cf6;">{xp}</p>
                <p style="margin: 5px 0 0; font-size: 12px; color: #6b7280;">XP Earned</p>
              </div>
            </td>
          </tr>
        </table>
        
        {achievements_section}
        
        <p style="margin: 0 0 25px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          {"Great work! Keep the momentum going." if generations_this_week > 0 else "No resumes generated this week? Let's change that!"} Your next interview could be one resume away.
        </p>
        
        <div style="text-align: center; margin: 30px 0;">
          {_cta_button("Generate New Resume", f"{APP_URL}/app")}
        </div>
      </td>
    </tr>
    """
    
    return subject, _base_template(content)


def get_achievement_email(
    name: str, 
    achievement_name: str, 
    achievement_description: str,
    xp_earned: int
) -> Tuple[str, str]:
    """Achievement unlocked celebration"""
    subject = f"Badge Unlocked: {achievement_name}!"
    
    content = f"""
    <tr>
      <td style="padding: 30px; text-align: center;">
        <div style="font-size: 64px; margin-bottom: 20px;">🏆</div>
        
        <h2 style="margin: 0 0 10px; font-size: 24px; color: #1f2937;">Achievement Unlocked!</h2>
        
        <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 16px; padding: 25px; margin: 25px 0; display: inline-block;">
          <p style="margin: 0 0 8px; font-size: 22px; font-weight: 700; color: #92400e;">{achievement_name}</p>
          <p style="margin: 0; font-size: 14px; color: #b45309;">{achievement_description}</p>
        </div>
        
        <p style="margin: 20px 0; font-size: 18px; color: #4b5563;">
          +{xp_earned} XP earned!
        </p>
        
        <p style="margin: 0 0 25px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          Congratulations, {name}! You're making great progress on your job hunt journey. Keep going!
        </p>
        
        <div style="margin: 30px 0;">
          {_cta_button("See All Achievements", f"{APP_URL}/app")}
        </div>
        
        <p style="margin: 20px 0 0; font-size: 14px; color: #6b7280;">
          Share your achievement on LinkedIn and inspire others!
        </p>
      </td>
    </tr>
    """
    
    return subject, _base_template(content)


def get_interview_celebration_email(name: str, company: str, title: str) -> Tuple[str, str]:
    """Interview celebration - encouragement and momentum"""
    subject = f"Amazing news, {name}! You got an interview!"
    
    content = f"""
    <tr>
      <td style="padding: 30px; text-align: center;">
        <div style="font-size: 64px; margin-bottom: 20px;">🎯</div>
        
        <h2 style="margin: 0 0 20px; font-size: 24px; color: #1f2937;">You Got an Interview!</h2>
        
        <p style="margin: 0 0 20px; font-size: 18px; color: #4b5563;">
          Congratulations, {name}! Your tailored resume worked.
        </p>
        
        <div style="background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%); border-radius: 16px; padding: 25px; margin: 25px 0;">
          <p style="margin: 0 0 8px; font-size: 20px; font-weight: 700; color: #065f46;">{title}</p>
          <p style="margin: 0; font-size: 16px; color: #047857;">at {company}</p>
        </div>
        
        <p style="margin: 0 0 25px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          This is a huge step! Here are some tips for your interview:
        </p>
        
        <ul style="margin: 0 0 25px; padding-left: 20px; font-size: 15px; line-height: 1.8; color: #4b5563; text-align: left;">
          <li>Research the company thoroughly</li>
          <li>Practice common interview questions</li>
          <li>Prepare questions to ask them</li>
          <li>Review the job description again</li>
        </ul>
        
        <div style="margin: 30px 0;">
          {_cta_button("Prepare More Applications", f"{APP_URL}/app", "#10b981")}
        </div>
        
        <p style="margin: 0; font-size: 14px; color: #6b7280;">
          You've got this! 💪
        </p>
      </td>
    </tr>
    """
    
    return subject, _base_template(content)


def get_job_landed_email(name: str, company: str, title: str) -> Tuple[str, str]:
    """Job landed celebration - biggest win"""
    subject = f"CONGRATULATIONS {name}! You landed the job! 🎉"
    
    content = f"""
    <tr>
      <td style="padding: 30px; text-align: center;">
        <div style="font-size: 80px; margin-bottom: 20px;">🎉</div>
        
        <h2 style="margin: 0 0 20px; font-size: 28px; color: #1f2937;">YOU DID IT!</h2>
        
        <p style="margin: 0 0 20px; font-size: 18px; color: #4b5563;">
          {name}, this is the moment you've been working toward!
        </p>
        
        <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 16px; padding: 30px; margin: 25px 0;">
          <p style="margin: 0 0 5px; font-size: 14px; color: #92400e;">YOUR NEW ROLE</p>
          <p style="margin: 0 0 8px; font-size: 24px; font-weight: 700; color: #78350f;">{title}</p>
          <p style="margin: 0; font-size: 18px; color: #92400e;">at {company}</p>
        </div>
        
        <p style="margin: 0 0 25px; font-size: 16px; line-height: 1.6; color: #4b5563;">
          Your hard work paid off. The tailored resumes, the applications, the interviews - it all led to this moment.
        </p>
        
        <div style="background-color: #f3f4f6; border-radius: 12px; padding: 20px; margin: 20px 0;">
          <p style="margin: 0 0 10px; font-size: 15px; font-weight: 600; color: #374151;">Help others succeed too!</p>
          <p style="margin: 0; font-size: 14px; color: #6b7280;">
            Share your success story on LinkedIn and tag @UmukoziHR. Your journey could inspire someone else!
          </p>
        </div>
        
        <div style="margin: 30px 0;">
          {_cta_button("Share on LinkedIn", "https://www.linkedin.com/sharing/share-offsite/", "#0077b5")}
        </div>
        
        <p style="margin: 20px 0 0; font-size: 14px; color: #6b7280;">
          Thank you for being part of the UmukoziHR family. We're so proud of you! 🧡
        </p>
      </td>
    </tr>
    """
    
    return subject, _base_template(content)


def get_broadcast_email(name: str, subject: str, content: str) -> Tuple[str, str]:
    """Admin broadcast email - custom content"""
    html_content = f"""
    <tr>
      <td style="padding: 30px;">
        <h2 style="margin: 0 0 20px; font-size: 24px; color: #1f2937;">Hey {name},</h2>
        
        <div style="font-size: 16px; line-height: 1.6; color: #4b5563;">
          {content.replace(chr(10), '<br>')}
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
          {_cta_button("Go to UmukoziHR", f"{APP_URL}/app")}
        </div>
      </td>
    </tr>
    """
    
    return subject, _base_template(html_content)
