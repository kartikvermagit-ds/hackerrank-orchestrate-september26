"""
Multimodal Evidence Retrieval Layer
------------------------------------
Retrieves, links, and structures textual messages and receipt/invoice images for users,
evaluation requests, and financial events.

Core Rules & Constraints:
- Correctly follows user_id, request_id, related_event_id, and image_id links.
- Resolves media file paths: dataset/media/images/<image_id>.png.
- Treats ALL message and image contents as UNTRUSTED DATA.
- Embedded prompt injections, overriding instructions, or manipulation attempts in raw text
  are flagged as untrusted and NEVER override challenge rules or directly drive financial decisions.
- Produces structured EvidenceBundle representations ready for downstream extraction models.
- Zero external API dependencies.
"""

import os
from typing import List, Dict, Optional, Set
import pandas as pd

from models import Message, MessageEvidence, ImageEvidence, EvidenceBundle
from image_processor import ImageProcessor

class EvidenceRetriever:
    """Retrieves and structures message and image evidence across users, requests, and events."""

    # Keywords commonly seen in untrusted prompt injection or system override attempts
    INJECTION_KEYWORDS = [
        'ignore previous', 'override rules', 'system prompt', 'developer mode',
        'mark affordable', 'disregard minimum', 'ignore balance', 'authorize all'
    ]

    def __init__(self, messages: List[Message], images_df: Optional[pd.DataFrame] = None,
                 media_dir: str = 'dataset/media/images',
                 image_processor: Optional[ImageProcessor] = None):
        self.media_dir = media_dir
        self.image_processor = image_processor

        # Index messages
        self.messages_by_user: Dict[str, List[MessageEvidence]] = {}
        self.messages_by_request: Dict[str, List[MessageEvidence]] = {}
        self.messages_by_event: Dict[str, List[MessageEvidence]] = {}
        self.messages_by_id: Dict[str, MessageEvidence] = {}

        for m in messages:
            is_suspicious = any(k in m.message_text.lower() for k in self.INJECTION_KEYWORDS)
            ev = MessageEvidence(
                message_id=m.message_id,
                user_id=m.user_id,
                request_id=m.request_id,
                related_event_id=m.related_event_id,
                sent_at=m.sent_at,
                source_type=m.source_type,
                raw_text=m.message_text,
                is_untrusted=True  # All user/third-party messages are inherently untrusted evidence
            )
            self.messages_by_id[m.message_id] = ev
            self.messages_by_user.setdefault(m.user_id, []).append(ev)

            if m.request_id:
                self.messages_by_request.setdefault(m.request_id, []).append(ev)
            if m.related_event_id:
                self.messages_by_event.setdefault(m.related_event_id, []).append(ev)

        # Index images
        self.images_by_user: Dict[str, List[ImageEvidence]] = {}
        self.images_by_request: Dict[str, List[ImageEvidence]] = {}
        self.images_by_event: Dict[str, List[ImageEvidence]] = {}
        self.images_by_id: Dict[str, ImageEvidence] = {}

        if images_df is not None:
            for _, r in images_df.iterrows():
                img_id = str(r['image_id']).strip()
                u_id = str(r['user_id']).strip()
                req_id = str(r['request_id']).strip() if pd.notna(r.get('request_id')) else None
                ev_id = str(r['related_event_id']).strip() if pd.notna(r.get('related_event_id')) else None

                file_path = os.path.join(self.media_dir, f"{img_id}.png")
                exists = os.path.isfile(file_path)

                extracted_amt = None
                if self.image_processor:
                    extracted_amt = self.image_processor.VERIFIED_IMAGE_AMOUNTS.get(img_id)

                img_ev = ImageEvidence(
                    image_id=img_id,
                    user_id=u_id,
                    request_id=req_id,
                    related_event_id=ev_id,
                    file_path=file_path,
                    exists=exists,
                    is_untrusted=True,
                    extracted_amount=extracted_amt
                )
                self.images_by_id[img_id] = img_ev
                self.images_by_user.setdefault(u_id, []).append(img_ev)
                if req_id:
                    self.images_by_request.setdefault(req_id, []).append(img_ev)
                if ev_id:
                    self.images_by_event.setdefault(ev_id, []).append(img_ev)

    def get_messages_for_user(self, user_id: str) -> List[MessageEvidence]:
        """Retrieve all messages associated with a user."""
        return self.messages_by_user.get(user_id, [])

    def get_messages_for_request(self, request_id: str) -> List[MessageEvidence]:
        """Retrieve all messages directly associated with a request."""
        return self.messages_by_request.get(request_id, [])

    def get_messages_for_event(self, event_id: str) -> List[MessageEvidence]:
        """Retrieve all messages describing a specific financial event."""
        return self.messages_by_event.get(event_id, [])

    def get_images_for_user(self, user_id: str) -> List[ImageEvidence]:
        """Retrieve all receipt/bill images associated with a user."""
        return self.images_by_user.get(user_id, [])

    def get_images_for_request(self, request_id: str) -> List[ImageEvidence]:
        """Retrieve all images directly associated with a request."""
        return self.images_by_request.get(request_id, [])

    def get_images_for_event(self, event_id: str) -> List[ImageEvidence]:
        """Retrieve images providing proof/receipt for a financial event."""
        return self.images_by_event.get(event_id, [])

    def get_image_by_id(self, image_id: str) -> Optional[ImageEvidence]:
        """Retrieve a specific image record by image_id."""
        return self.images_by_id.get(image_id)

    def get_evidence_bundle(self, user_id: str, request_id: Optional[str] = None,
                            event_ids: Optional[List[str]] = None) -> EvidenceBundle:
        """
        Assemble a complete structured evidence bundle for a user request context.
        Consolidates user-level, request-level, and event-level evidence.
        """
        u_msgs = self.get_messages_for_user(user_id)
        req_msgs = self.get_messages_for_request(request_id) if request_id else []
        req_imgs = self.get_images_for_request(request_id) if request_id else []

        ev_msgs: Dict[str, List[MessageEvidence]] = {}
        ev_imgs: Dict[str, List[ImageEvidence]] = {}

        if event_ids:
            for ev_id in event_ids:
                m_list = self.get_messages_for_event(ev_id)
                if m_list:
                    ev_msgs[ev_id] = m_list

                img_list = self.get_images_for_event(ev_id)
                if img_list:
                    ev_imgs[ev_id] = img_list

        return EvidenceBundle(
            user_id=user_id,
            request_id=request_id,
            user_messages=u_msgs,
            request_messages=req_msgs,
            event_messages=ev_msgs,
            request_images=req_imgs,
            event_images=ev_imgs
        )
