"""Ignore rule repository."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models import IgnoreRule
from app.models.ignore_rule import IgnoreRuleType


class IgnoreRuleRepository(BaseRepository[IgnoreRule]):
    """Repository for ignore rule operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, IgnoreRule)

    async def list(
        self,
        *,
        device_id: UUID,
        skip: int = 0,
        limit: int = 50,
        rule_type: IgnoreRuleType | None = None,
    ) -> tuple[list[IgnoreRule], int]:
        """List ignore rules for a device with optional filtering."""
        # Build base query
        base_query = select(IgnoreRule).where(IgnoreRule.device_id == device_id)

        if rule_type:
            base_query = base_query.where(IgnoreRule.rule_type == rule_type)

        # Count total
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get items
        stmt = base_query.order_by(IgnoreRule.created_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_by_device(self, device_id: UUID, rule_id: UUID) -> IgnoreRule | None:
        """Get an ignore rule ensuring it belongs to the device."""
        stmt = select(IgnoreRule).where(
            IgnoreRule.id == rule_id,
            IgnoreRule.device_id == device_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_for_device(self, device_id: UUID) -> list[IgnoreRule]:
        """Get all ignore rules for a device."""
        stmt = select(IgnoreRule).where(IgnoreRule.device_id == device_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def should_ignore(self, device_id: UUID, message: dict[str, Any]) -> bool:
        """Check if a message should be ignored based on rules."""
        rules = await self.get_all_for_device(device_id)

        sender_jid = message.get("sender_jid", "")
        group_name = message.get("group_name", "")
        content = message.get("content", "")
        is_group = message.get("is_group", False)

        for rule in rules:
            if rule.rule_type == IgnoreRuleType.CONTACT:
                # Check if sender JID matches the pattern
                if re.search(rule.pattern, sender_jid, re.IGNORECASE):
                    return True

            elif rule.rule_type == IgnoreRuleType.GROUP:
                # Check if it's a group and name matches
                if is_group and re.search(rule.pattern, group_name, re.IGNORECASE):
                    return True

            elif rule.rule_type == IgnoreRuleType.KEYWORD:
                # Check if content contains the keyword
                if re.search(rule.pattern, content, re.IGNORECASE):
                    return True

        return False
