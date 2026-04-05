import io
import logging

import pydub
from google.cloud import texttospeech
from google.auth import impersonated_credentials
import google.auth
import google.auth.transport.requests

from alarmpi.core import aptts


event_logger = logging.getLogger("eventLogger")


class GoogleCloudTTS(aptts.AlarmpiTTS):
    """A Google Cloud Text-to-Speech client.
    
    Uses a WaveNet voice for more human-like speech.
    The monthly free tier of 1 million charaters
    should easily cover the requirements for running the alarm once a day.

    For API limits and pricing, see
    https://cloud.google.com/text-to-speech/quotas
    https://cloud.google.com/text-to-speech/pricing
    """

    def __init__(self, auth: dict):
        super().__init__()
        self.auth = auth
        self.client = self.get_client()

    def get_client(self):
        """Create a TextToSpeechClient client using either impersonated 
        service account credentials from config or ADC credentials
        detected from environment.
        
        Fails if neither is available.
        """

        if self.auth:
            service_account = self.auth["service_account"]
            event_logger.info("Fetching credentials for %s", service_account)
            credentials = fetch_service_account_access_token(service_account)
        else:
            event_logger.info("No explicit credentials provided, trying to detect credentials from environment.")
            credentials, _ = google.auth.default()

        client = texttospeech.TextToSpeechClient(credentials=credentials)
        event_logger.info("Success!")
        return client

    def setup(self, text: str):
        """Synthesize text as speech.
        
        Args:
            text (str): the content to synthesize
        Return:
            the synthesized speech as pydub.AudioSegment
        """
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Build the voice request and specify a WaveNet voice for more human like speech.
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Wavenet-C"
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        # Perform the text-to-speech request.
        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        f = io.BytesIO(response.audio_content)
        return pydub.AudioSegment.from_file(f, format="mp3")


def fetch_service_account_access_token(
    impersonated_service_account: str
):
    """
    Fetch short lived impersonation credentials for a service account.
    Requires source credentials to initiate the impersonation
    (eg. active local user credentials).

    Args:
        impersonated_service_account: The email of the service account to impersonate.
    Return:
        service account credentials.
    """

    # Get current caller identity.
    credentials, _ = google.auth.default()

    # Create the impersonated credential.
    target_credentials = impersonated_credentials.Credentials(
        source_credentials=credentials,
        target_principal=impersonated_service_account,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        lifetime=600,
    )

    # Get the OAuth2 token.
    request = google.auth.transport.requests.Request()
    target_credentials.refresh(request)

    return target_credentials
