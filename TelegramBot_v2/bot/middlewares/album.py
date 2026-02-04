"""
Middleware для обработки медиагрупп (альбомов).

Telegram отправляет фотографии из альбома как отдельные сообщения 
с одинаковым media_group_id. Этот middleware собирает их вместе 
и передаёт одним списком в обработчик.
"""

import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Union

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
import structlog


logger = structlog.get_logger()


class AlbumMiddleware(BaseMiddleware):
    """
    Middleware для сборки медиагрупп (альбомов) в один список.
    
    Когда пользователь отправляет несколько фото сразу, Telegram
    присылает их как отдельные сообщения с одним media_group_id.
    
    Этот middleware:
    1. Собирает все сообщения с одинаковым media_group_id
    2. Ждёт небольшую задержку для получения всех фото
    3. Передаёт список фото в обработчик через data["album"]
    """
    
    # Хранилище альбомов: {media_group_id: [messages]}
    _albums: Dict[str, List[Message]] = {}
    # Блокировки для предотвращения race condition
    _locks: Dict[str, asyncio.Lock] = {}
    # Задержка ожидания остальных фото альбома (секунды)
    ALBUM_LATENCY: float = 0.5
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Обработка входящего события.
        
        Если это сообщение с media_group_id:
        - Первое фото группы: создаём альбом, ждём остальные, вызываем handler
        - Последующие фото: добавляем в альбом, не вызываем handler
        
        Если это обычное сообщение без медиагруппы - передаём как есть.
        """
        if not isinstance(event, Message):
            return await handler(event, data)
        
        # Если нет media_group_id - обычное сообщение
        if not event.media_group_id:
            return await handler(event, data)
        
        media_group_id = event.media_group_id
        
        # Создаём lock для этой группы если нет
        if media_group_id not in self._locks:
            self._locks[media_group_id] = asyncio.Lock()
        
        async with self._locks[media_group_id]:
            # Первое сообщение в группе?
            is_first = media_group_id not in self._albums
            
            if is_first:
                # Создаём новый альбом
                self._albums[media_group_id] = [event]
                
                logger.debug(
                    "album_started",
                    media_group_id=media_group_id,
                    user_id=event.from_user.id if event.from_user else 0,
                )
            else:
                # Добавляем в существующий альбом
                self._albums[media_group_id].append(event)
                
                logger.debug(
                    "album_photo_added",
                    media_group_id=media_group_id,
                    count=len(self._albums[media_group_id]),
                )
        
        # Только первое сообщение запускает обработку
        if not is_first:
            return None
        
        # Ждём остальные фото альбома
        await asyncio.sleep(self.ALBUM_LATENCY)
        
        # Забираем собранный альбом
        async with self._locks[media_group_id]:
            album = self._albums.pop(media_group_id, [])
            # Очищаем lock
            if media_group_id in self._locks:
                del self._locks[media_group_id]
        
        if not album:
            return None
        
        # Сортируем по message_id для правильного порядка
        album.sort(key=lambda m: m.message_id)
        
        logger.info(
            "album_collected",
            media_group_id=media_group_id,
            photo_count=len(album),
            user_id=event.from_user.id if event.from_user else 0,
        )
        
        # Передаём альбом в data
        data["album"] = album
        data["is_album"] = True
        
        # Вызываем handler с первым сообщением и альбомом в data
        return await handler(event, data)
