"""Hindi / Indian-English speech with Amazon Polly, cached in S3 by text."""
import hashlib
import logging

from botocore.exceptions import ClientError

log = logging.getLogger(__name__)

VOICES = {"hi": ("Kajal", "hi-IN"), "en": ("Kajal", "en-IN")}


def audio_key(text, lang):
    voice, code = VOICES[lang]
    digest = hashlib.sha256(f"{voice}|{code}|{text}".encode()).hexdigest()[:32]
    return f"audio/{digest}.mp3"


class Audio:
    def __init__(self, polly, s3, bucket):
        self.polly, self.s3, self.bucket = polly, s3, bucket

    def _exists(self, key):
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as error:
            if error.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def ensure(self, text, lang):
        """S3 key of the speech for this text, synthesising it once; None if Polly fails."""
        key = audio_key(text, lang)
        if self._exists(key):
            return key
        voice, code = VOICES[lang]
        try:
            speech = self.polly.synthesize_speech(
                Text=text, VoiceId=voice, Engine="neural", LanguageCode=code, OutputFormat="mp3")
            body = speech["AudioStream"].read()
        except Exception as error:  # the page falls back to the phone's own voice
            log.warning("polly failed: %s", error)
            return None
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType="audio/mpeg")
        return key

    def url(self, key, expires=3600):
        return self.s3.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires)
