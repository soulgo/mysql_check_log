import pandas as pd
from datetime import datetime, timedelta
from models import UserActivity, db
from sqlalchemy import func, and_

class ReportGenerator:
    @staticmethod
    def generate_summary_report(start_date, end_date):
        """生成指定时间段的汇总报表"""
        activities = UserActivity.query.filter(
            and_(
                UserActivity.timestamp >= start_date,
                UserActivity.timestamp <= end_date
            )
        )

        # 按风险等级统计
        risk_stats = db.session.query(
            UserActivity.risk_level,
            func.count(UserActivity.id)
        ).filter(
            and_(
                UserActivity.timestamp >= start_date,
                UserActivity.timestamp <= end_date
            )
        ).group_by(UserActivity.risk_level).all()

        # 活跃用户统计
        active_users = db.session.query(
            UserActivity.user_name,
            func.count(UserActivity.id)
        ).filter(
            and_(
                UserActivity.timestamp >= start_date,
                UserActivity.timestamp <= end_date
            )
        ).group_by(UserActivity.user_name).all()

        # 按风险等级分类的操作类型统计
        high_risk_ops = db.session.query(
            UserActivity.operation_type,
            func.count(UserActivity.id)
        ).filter(
            and_(
                UserActivity.timestamp >= start_date,
                UserActivity.timestamp <= end_date,
                UserActivity.risk_level == 'High'
            )
        ).group_by(UserActivity.operation_type).all()

        medium_risk_ops = db.session.query(
            UserActivity.operation_type,
            func.count(UserActivity.id)
        ).filter(
            and_(
                UserActivity.timestamp >= start_date,
                UserActivity.timestamp <= end_date,
                UserActivity.risk_level == 'Medium'
            )
        ).group_by(UserActivity.operation_type).all()

        low_risk_ops = db.session.query(
            UserActivity.operation_type,
            func.count(UserActivity.id)
        ).filter(
            and_(
                UserActivity.timestamp >= start_date,
                UserActivity.timestamp <= end_date,
                UserActivity.risk_level == 'Low'
            )
        ).group_by(UserActivity.operation_type).all()

        return {
            'period': {
                'start': start_date,
                'end': end_date
            },
            'risk_level_summary': dict(risk_stats),
            'active_users': dict(active_users),
            'operation_types': {
                'high_risk': dict(high_risk_ops),
                'medium_risk': dict(medium_risk_ops),
                'low_risk': dict(low_risk_ops)
            },
            'total_operations': activities.count()
        }

    @staticmethod
    def export_activities(start_date, end_date, risk_levels=None, users=None, operation_types=None):
        """导出操作记录为DataFrame"""
        query = UserActivity.query.filter(
            and_(
                UserActivity.timestamp >= start_date,
                UserActivity.timestamp <= end_date
            )
        )

        if risk_levels:
            query = query.filter(UserActivity.risk_level.in_(risk_levels))
        if users:
            query = query.filter(UserActivity.user_name.in_(users))
        if operation_types:
            query = query.filter(UserActivity.operation_type.in_(operation_types))

        activities = query.all()
        
        data = []
        for activity in activities:
            data.append({
                '操作ID': activity.id,
                '服务器ID': activity.server_id,
                '用户名': activity.user_name,
                '操作时间': activity.timestamp,
                '客户端主机': activity.client_host,
                '数据库': activity.db_name,
                '操作类型': activity.operation_type,
                '风险等级': activity.risk_level,
                'SQL语句': activity.argument,
                '线程ID': activity.thread_id
            })
        
        return pd.DataFrame(data)

    @classmethod
    def generate_daily_report(cls):
        """生成日报"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        return cls.generate_summary_report(start_date, end_date)

    @classmethod
    def generate_weekly_report(cls):
        """生成周报"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        return cls.generate_summary_report(start_date, end_date)

    @classmethod
    def generate_monthly_report(cls):
        """生成月报"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        return cls.generate_summary_report(start_date, end_date) 