import io
import logging

import pydub
from google.cloud import texttospeech
from google.auth import impersonated_credentials
import google.auth.transport.requests

from alarmpi.core import aptts


event_logger = logging.getLogger("eventLogger")


class GoogleCloudTTS(aptts.AlarmpiTTS):
    """A Google Cloud Text-to-Speech client. This uses a WaveNet voice for more human-like
    speech and higher costs. However, the monthly free tier of 1 million charaters
    should easily cover the requirements for running the alarm once a day.

    For API limits and pricing, see
    https://cloud.google.com/text-to-speech/quotas
    https://cloud.google.com/text-to-speech/pricing
    """

    def __init__(self, auth):
        super().__init__()
        self.auth = auth
        self.client = self.get_client()

    def get_client(self):
        """Create an API client using the impersonated service account credentials."""
        self.credentials = fetch_service_account_access_token(self.auth["service_account"])
        client = texttospeech.TextToSpeechClient(credentials=self.credentials)
        return client

    def setup(self, text):
        """Create a TTS client and convert input to pydub audio."""
        # Set the text input to be synthesized
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Build the voice request and specify a WaveNet voice for more human like speech
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Wavenet-C"
        )

        # Select the type of audio file you want returned
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        # Perform the text-to-speech request on the text input with the selected
        # voice parameters and audio file type
        response = self.client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)

        f = io.BytesIO(response.audio_content)
        return pydub.AudioSegment.from_file(f, format="mp3")


def fetch_service_account_access_token(
    impersonated_service_account: str
):
    """
    Fetch short lived impersonation credentials for a service account.
    This requires the 
      "roles/iam.serviceAccountTokenCreator" permission on the target service account.

    Args:
        impersonated_service_account: The name of the privilege-bearing service account for whom the credential is created.
    """

    # Get current caller identity.
    credentials, project_id = google.auth.default()

    # Create the impersonated credential.
    event_logger.info("Fetching credentials for %s", impersonated_service_account)
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
