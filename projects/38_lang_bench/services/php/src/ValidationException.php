<?php

declare(strict_types=1);

namespace Bench;

/** リクエスト内容の不備。HTTP層で400に変換する。 */
final class ValidationException extends \RuntimeException
{
    public function __construct()
    {
        parent::__construct('validation_failed');
    }
}
