# -*- coding: utf-8 -*-
"""为 Machine Learning Foundations 演示课补充第 2、3 节课（本地测试用）。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from database import SessionLocal
from models.lecture import Bookmark, Lecture, LectureBriefing, Transcription

COURSE_ID = 11
BASE_LECTURE_ID = 33


LECTURES = [
    {
        "session_number": 2,
        "title": "Lecture 2: Logistic Regression and Classification",
        "lecture_date": date(2026, 8, 28),
        "started_at": datetime(2026, 8, 28, 9, 0),
        "ended_at": datetime(2026, 8, 28, 9, 45),
        "subject_tags": ["machine-learning", "logistic-regression", "classification"],
        "sentences": [
            (
                "Today we move from regression to classification with logistic regression.",
                "今天我们从回归转到分类，学习逻辑回归。",
                False,
                None,
            ),
            (
                "Classification predicts discrete labels such as spam or not spam.",
                "分类预测离散标签，例如垃圾邮件或非垃圾邮件。",
                True,
                "definition",
            ),
            (
                "The sigmoid function maps any real number into a probability between zero and one.",
                "Sigmoid 函数把任意实数映射到 0 到 1 之间的概率。",
                True,
                "definition",
            ),
            (
                "We interpret the model output as the probability that y equals one given x.",
                "我们把模型输出解释为在给定 x 时 y 等于 1 的概率。",
                False,
                None,
            ),
            (
                "The decision boundary is the set of points where the predicted probability equals one half.",
                "决策边界是预测概率等于二分之一的点集。",
                True,
                "important",
            ),
            (
                "Cross-entropy loss penalizes confident wrong predictions more heavily than squared error.",
                "交叉熵损失对自信但错误的预测惩罚比平方误差更重。",
                True,
                "important",
            ),
            (
                "Gradient descent still works, but the cost surface for logistic regression is convex.",
                "梯度下降仍然可用，而且逻辑回归的代价曲面是凸的。",
                False,
                None,
            ),
            (
                "Precision and recall help when classes are imbalanced and accuracy is misleading.",
                "类别不平衡时，精确率和召回率比准确率更有用。",
                True,
                "question",
            ),
            (
                "A confusion matrix summarizes true positives, false positives, true negatives and false negatives.",
                "混淆矩阵汇总真正例、假正例、真负例和假负例。",
                True,
                "exam",
            ),
            (
                "Regularization with L2 keeps weights small and reduces overfitting on sparse features.",
                "L2 正则化压小权重，减轻稀疏特征上的过拟合。",
                False,
                None,
            ),
            (
                "Homework: fit logistic regression on a binary dataset and plot the decision boundary.",
                "作业：在二分类数据上拟合逻辑回归，并画出决策边界。",
                True,
                "exam",
            ),
            (
                "Next class we will introduce neural networks and the intuition behind backpropagation.",
                "下节课我们介绍神经网络，以及反向传播的直觉。",
                True,
                "important",
            ),
        ],
        "overview": (
            "本节从线性回归过渡到分类问题，讲解逻辑回归、Sigmoid、决策边界、"
            "交叉熵损失，以及精确率/召回率与混淆矩阵。"
        ),
        "outline": [
            {
                "title": "从回归到分类",
                "summary": "引入分类任务与逻辑回归。",
                "start_order": 1,
                "end_order": 2,
                "start_offset_ms": 0,
            },
            {
                "title": "Sigmoid 与概率解释",
                "summary": "用 Sigmoid 输出概率，并定义决策边界。",
                "start_order": 3,
                "end_order": 5,
                "start_offset_ms": 420000,
            },
            {
                "title": "损失与优化",
                "summary": "交叉熵损失与凸优化性质。",
                "start_order": 6,
                "end_order": 7,
                "start_offset_ms": 1050000,
            },
            {
                "title": "评估指标",
                "summary": "精确率、召回率与混淆矩阵。",
                "start_order": 8,
                "end_order": 9,
                "start_offset_ms": 1470000,
            },
            {
                "title": "正则化与作业",
                "summary": "L2 正则化、作业与下节预告。",
                "start_order": 10,
                "end_order": 12,
                "start_offset_ms": 1890000,
            },
        ],
        "key_points": [
            {
                "tag": "definition",
                "text": "分类预测离散标签，例如垃圾邮件或非垃圾邮件。",
                "source_text": "Classification predicts discrete labels such as spam or not spam.",
                "sentence_order": 2,
                "start_offset_ms": 210000,
            },
            {
                "tag": "definition",
                "text": "Sigmoid 函数把任意实数映射到 0 到 1 之间的概率。",
                "source_text": (
                    "The sigmoid function maps any real number into a probability "
                    "between zero and one."
                ),
                "sentence_order": 3,
                "start_offset_ms": 420000,
            },
            {
                "tag": "important",
                "text": "决策边界是预测概率等于二分之一的点集。",
                "source_text": (
                    "The decision boundary is the set of points where the predicted "
                    "probability equals one half."
                ),
                "sentence_order": 5,
                "start_offset_ms": 840000,
            },
            {
                "tag": "exam",
                "text": "混淆矩阵汇总真正例、假正例、真负例和假负例。",
                "source_text": (
                    "A confusion matrix summarizes true positives, false positives, "
                    "true negatives and false negatives."
                ),
                "sentence_order": 9,
                "start_offset_ms": 1680000,
            },
        ],
        "terms": [
            {
                "term": "逻辑回归",
                "explanation": "用于二分类的概率模型，输出经 Sigmoid 映射。",
                "source_text": (
                    "Today we move from regression to classification with logistic regression."
                ),
                "sentence_order": 1,
                "start_offset_ms": 0,
            },
            {
                "term": "Sigmoid",
                "explanation": "将实数映射到 (0,1) 的 S 形函数。",
                "source_text": (
                    "The sigmoid function maps any real number into a probability "
                    "between zero and one."
                ),
                "sentence_order": 3,
                "start_offset_ms": 420000,
            },
            {
                "term": "交叉熵损失",
                "explanation": "对自信错误预测惩罚更重的分类损失。",
                "source_text": (
                    "Cross-entropy loss penalizes confident wrong predictions more "
                    "heavily than squared error."
                ),
                "sentence_order": 6,
                "start_offset_ms": 1050000,
            },
            {
                "term": "混淆矩阵",
                "explanation": "按真伪正负例统计分类结果的表格。",
                "source_text": (
                    "A confusion matrix summarizes true positives, false positives, "
                    "true negatives and false negatives."
                ),
                "sentence_order": 9,
                "start_offset_ms": 1680000,
            },
        ],
        "assignments": [
            {
                "text": "在二分类数据上拟合逻辑回归，并画出决策边界。",
                "due_date": None,
                "source_text": (
                    "Homework: fit logistic regression on a binary dataset and plot "
                    "the decision boundary."
                ),
                "sentence_order": 11,
                "start_offset_ms": 2100000,
                "needs_confirmation": True,
            },
            {
                "text": "预习神经网络与反向传播的基本直觉。",
                "due_date": None,
                "source_text": (
                    "Next class we will introduce neural networks and the intuition "
                    "behind backpropagation."
                ),
                "sentence_order": 12,
                "start_offset_ms": 2310000,
                "needs_confirmation": True,
            },
        ],
        "exam_hints": [
            {
                "text": "说明 Sigmoid 输出如何解释为概率，以及决策边界取 0.5 的含义。",
                "sentence_order": 3,
                "start_offset_ms": 420000,
            },
            {
                "text": "对比准确率与精确率/召回率，解释类别不平衡时为何不能只看准确率。",
                "sentence_order": 8,
                "start_offset_ms": 1470000,
            },
        ],
        "questions": [
            {
                "text": "为什么逻辑回归的代价函数通常选用交叉熵而不是均方误差？",
                "sentence_order": 6,
                "start_offset_ms": 1050000,
            },
            {
                "text": "L2 正则化如何帮助稀疏特征上的分类模型？",
                "sentence_order": 10,
                "start_offset_ms": 1890000,
            },
        ],
    },
    {
        "session_number": 3,
        "title": "Lecture 3: Neural Networks and Backpropagation",
        "lecture_date": date(2026, 9, 2),
        "started_at": datetime(2026, 9, 2, 9, 0),
        "ended_at": datetime(2026, 9, 2, 9, 45),
        "subject_tags": ["machine-learning", "neural-networks", "backpropagation"],
        "sentences": [
            (
                "Today we introduce neural networks as stacked nonlinear transformations.",
                "今天我们把神经网络理解为堆叠的非线性变换。",
                False,
                None,
            ),
            (
                "A neuron computes a weighted sum of inputs and then applies an activation function.",
                "一个神经元先对输入加权求和，再经过激活函数。",
                True,
                "definition",
            ),
            (
                "Common activations include ReLU, sigmoid, and tanh; ReLU is popular for deep networks.",
                "常见激活有 ReLU、Sigmoid 和 Tanh；深度网络常用 ReLU。",
                True,
                "important",
            ),
            (
                "Hidden layers let the model learn hierarchical features beyond linear decision boundaries.",
                "隐层让模型学到层次化特征，超越线性决策边界。",
                True,
                "definition",
            ),
            (
                "Forward propagation computes layer outputs from input to the final prediction.",
                "前向传播从输入逐层计算，直到得到最终预测。",
                False,
                None,
            ),
            (
                "Backpropagation uses the chain rule to compute gradients of the loss with respect to each weight.",
                "反向传播用链式法则计算损失对每个权重的梯度。",
                True,
                "exam",
            ),
            (
                "Vanishing gradients can slow learning in deep sigmoid networks; ReLU mitigates this issue.",
                "深层 Sigmoid 网络可能梯度消失；ReLU 能缓解这个问题。",
                True,
                "question",
            ),
            (
                "Mini-batch stochastic gradient descent updates weights using small subsets of the training data.",
                "小批量随机梯度下降用训练集的小子集更新权重。",
                True,
                "important",
            ),
            (
                "Dropout randomly disables units during training to reduce co-adaptation and overfitting.",
                "Dropout 在训练时随机关闭单元，减轻共适应与过拟合。",
                False,
                None,
            ),
            (
                "Always monitor training and validation loss to detect underfitting or overfitting early.",
                "始终观察训练与验证损失，尽早发现欠拟合或过拟合。",
                True,
                "exam",
            ),
            (
                "Homework: implement a two-layer network with backpropagation for XOR, and plot training loss.",
                "作业：用反向传播实现两层网络解决 XOR，并画出训练损失。",
                True,
                "exam",
            ),
            (
                "Next week we will discuss convolutional networks for images and transfer learning basics.",
                "下周讨论用于图像的卷积网络，以及迁移学习基础。",
                True,
                "important",
            ),
        ],
        "overview": (
            "本节介绍神经网络结构、激活函数、前向/反向传播、梯度消失与小批量 SGD，"
            "并布置 XOR 实验作业。"
        ),
        "outline": [
            {
                "title": "神经元与激活",
                "summary": "加权和、激活函数与 ReLU。",
                "start_order": 1,
                "end_order": 3,
                "start_offset_ms": 0,
            },
            {
                "title": "隐层与前向传播",
                "summary": "层次特征与逐层前向计算。",
                "start_order": 4,
                "end_order": 5,
                "start_offset_ms": 630000,
            },
            {
                "title": "反向传播与训练技巧",
                "summary": "链式法则、梯度消失、小批量 SGD 与 Dropout。",
                "start_order": 6,
                "end_order": 9,
                "start_offset_ms": 1050000,
            },
            {
                "title": "监控、作业与预告",
                "summary": "损失曲线、XOR 作业与卷积网络预告。",
                "start_order": 10,
                "end_order": 12,
                "start_offset_ms": 1890000,
            },
        ],
        "key_points": [
            {
                "tag": "definition",
                "text": "神经元先对输入加权求和，再经过激活函数。",
                "source_text": (
                    "A neuron computes a weighted sum of inputs and then applies an "
                    "activation function."
                ),
                "sentence_order": 2,
                "start_offset_ms": 210000,
            },
            {
                "tag": "definition",
                "text": "隐层让模型学到层次化特征，超越线性决策边界。",
                "source_text": (
                    "Hidden layers let the model learn hierarchical features beyond "
                    "linear decision boundaries."
                ),
                "sentence_order": 4,
                "start_offset_ms": 630000,
            },
            {
                "tag": "exam",
                "text": "反向传播用链式法则计算损失对每个权重的梯度。",
                "source_text": (
                    "Backpropagation uses the chain rule to compute gradients of the "
                    "loss with respect to each weight."
                ),
                "sentence_order": 6,
                "start_offset_ms": 1050000,
            },
            {
                "tag": "important",
                "text": "小批量随机梯度下降用训练集的小子集更新权重。",
                "source_text": (
                    "Mini-batch stochastic gradient descent updates weights using "
                    "small subsets of the training data."
                ),
                "sentence_order": 8,
                "start_offset_ms": 1470000,
            },
        ],
        "terms": [
            {
                "term": "神经元",
                "explanation": "加权求和后再经激活函数的基本计算单元。",
                "source_text": (
                    "A neuron computes a weighted sum of inputs and then applies an "
                    "activation function."
                ),
                "sentence_order": 2,
                "start_offset_ms": 210000,
            },
            {
                "term": "反向传播",
                "explanation": "用链式法则把损失梯度传回各层权重。",
                "source_text": (
                    "Backpropagation uses the chain rule to compute gradients of the "
                    "loss with respect to each weight."
                ),
                "sentence_order": 6,
                "start_offset_ms": 1050000,
            },
            {
                "term": "梯度消失",
                "explanation": "深层网络中梯度过小导致学习变慢的现象。",
                "source_text": (
                    "Vanishing gradients can slow learning in deep sigmoid networks; "
                    "ReLU mitigates this issue."
                ),
                "sentence_order": 7,
                "start_offset_ms": 1260000,
            },
            {
                "term": "Dropout",
                "explanation": "训练时随机关闭单元以减轻过拟合的正则手段。",
                "source_text": (
                    "Dropout randomly disables units during training to reduce "
                    "co-adaptation and overfitting."
                ),
                "sentence_order": 9,
                "start_offset_ms": 1680000,
            },
        ],
        "assignments": [
            {
                "text": "用反向传播实现两层网络解决 XOR，并画出训练损失。",
                "due_date": None,
                "source_text": (
                    "Homework: implement a two-layer network with backpropagation for "
                    "XOR, and plot training loss."
                ),
                "sentence_order": 11,
                "start_offset_ms": 2100000,
                "needs_confirmation": True,
            },
            {
                "text": "预习卷积网络与迁移学习基础。",
                "due_date": None,
                "source_text": (
                    "Next week we will discuss convolutional networks for images and "
                    "transfer learning basics."
                ),
                "sentence_order": 12,
                "start_offset_ms": 2310000,
                "needs_confirmation": True,
            },
        ],
        "exam_hints": [
            {
                "text": "用链式法则说明反向传播如何得到某一层权重的梯度。",
                "sentence_order": 6,
                "start_offset_ms": 1050000,
            },
            {
                "text": "解释为何深层 Sigmoid 网络容易梯度消失，以及 ReLU 如何缓解。",
                "sentence_order": 7,
                "start_offset_ms": 1260000,
            },
        ],
        "questions": [
            {
                "text": "为什么单层感知机无法解决 XOR，而两层网络可以？",
                "sentence_order": 4,
                "start_offset_ms": 630000,
            },
            {
                "text": "如何从训练/验证损失曲线判断欠拟合与过拟合？",
                "sentence_order": 10,
                "start_offset_ms": 1890000,
            },
        ],
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        base = db.query(Lecture).filter(Lecture.id == BASE_LECTURE_ID).one()
        existing = (
            db.query(Lecture)
            .filter(Lecture.course_id == COURSE_ID)
            .order_by(Lecture.session_number)
            .all()
        )
        print("before:", [(l.id, l.session_number, l.title) for l in existing])
        taken = {l.session_number for l in existing}
        if 2 in taken or 3 in taken:
            print("session 2/3 already exist; nothing to do")
            return

        created = []
        for spec in LECTURES:
            lecture = Lecture(
                user_id=base.user_id,
                course_id=COURSE_ID,
                session_number=spec["session_number"],
                course_name=base.course_name,
                title=spec["title"],
                source_lang=base.source_lang,
                target_lang=base.target_lang,
                translation_enabled=True,
                duration_seconds=2700,
                sentence_count=len(spec["sentences"]),
                bookmark_count=sum(1 for item in spec["sentences"] if item[2]),
                room=base.room,
                subject_tags=spec["subject_tags"],
                status="completed",
                lecture_date=spec["lecture_date"],
                started_at=spec["started_at"],
                ended_at=spec["ended_at"],
            )
            db.add(lecture)
            db.flush()

            for i, (src, tr, bookmarked, tag) in enumerate(spec["sentences"], start=1):
                tx = Transcription(
                    lecture_id=lecture.id,
                    user_id=base.user_id,
                    source_text=src,
                    source_lang="en",
                    translated_text=tr,
                    target_lang="zh-CN",
                    engine="seed",
                    mode="online",
                    sentence_order=i,
                    start_offset_ms=(i - 1) * 210000,
                    end_offset_ms=i * 210000,
                    recorded_at=spec["started_at"]
                    + timedelta(milliseconds=(i - 1) * 210000),
                    is_bookmarked=bookmarked,
                )
                db.add(tx)
                db.flush()
                if bookmarked and tag:
                    db.add(
                        Bookmark(
                            user_id=base.user_id,
                            transcription_id=tx.id,
                            lecture_id=lecture.id,
                            tag=tag,
                            note=None,
                        )
                    )

            db.add(
                LectureBriefing(
                    lecture_id=lecture.id,
                    user_id=base.user_id,
                    status="ready",
                    edit_status="auto",
                    provider="seed:demo",
                    overview=spec["overview"],
                    outline=spec["outline"],
                    key_points=spec["key_points"],
                    exam_hints=spec["exam_hints"],
                    questions=spec["questions"],
                    terms=spec["terms"],
                    assignments=spec["assignments"],
                    source_sentence_count=len(spec["sentences"]),
                    generated_at=datetime.now(),
                )
            )
            created.append(
                (
                    lecture.id,
                    lecture.session_number,
                    lecture.title,
                    lecture.sentence_count,
                    lecture.bookmark_count,
                )
            )

        db.commit()
        print("created:", created)
        after = (
            db.query(Lecture)
            .filter(Lecture.course_id == COURSE_ID)
            .order_by(Lecture.session_number)
            .all()
        )
        print("after:", [(l.id, l.session_number, l.title, l.status) for l in after])
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
