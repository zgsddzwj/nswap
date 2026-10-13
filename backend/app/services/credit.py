"""信用事件：只累计客观数据（成交/评价/感谢/违约），不做综合评分。"""

from sqlalchemy.orm import Session

from app.models import Item, Review, Transaction, User


def on_trade_completed(db: Session, trade: Transaction, item: Item, owner: User, other: User) -> None:
    if item.type == "want":
        # 求购帖：owner 是收受方，other 是提供方（计一次让出）
        other.give_done += 1
        return
    if item.type == "sell":
        owner.sell_done += 1
    elif item.type == "give":
        owner.give_done += 1
    elif item.type == "swap":
        owner.swap_done += 1


def on_review(db: Session, review: Review, to_user: User) -> None:
    if review.rating == 3:
        to_user.review_good += 1
    elif review.rating == 2:
        to_user.review_mid += 1
    else:
        to_user.review_bad += 1


def on_violation(db: Session, user: User) -> None:
    user.violations += 1


def on_gratitude_thanked(db: Session, thanked_user: User) -> None:
    thanked_user.thanks_count += 1
