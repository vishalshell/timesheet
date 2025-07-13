#!/usr/bin/env python3
"""
Comprehensive Backend Testing Suite for Timesheet Management System
Tests JWT Authentication, User Management, Project CRUD, Timesheet Management, 
Approval Workflow, and Dashboard Analytics
"""

import requests
import json
from datetime import datetime, timedelta
import time

# Backend URL from frontend .env
BASE_URL = "https://82d3d7b2-1297-41d3-adc6-927f55d8a564.preview.emergentagent.com/api"

class TimesheetBackendTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.tokens = {}
        self.users = {}
        self.projects = {}
        self.timesheets = {}
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        
    def test_user_registration(self):
        """Test user registration for different roles"""
        self.log("=== Testing User Registration ===")
        
        test_users = [
            {
                "email": "admin@company.com",
                "username": "admin_user",
                "full_name": "System Administrator",
                "password": "admin123!",
                "role": "admin"
            },
            {
                "email": "manager@company.com", 
                "username": "manager_user",
                "full_name": "Project Manager",
                "password": "manager123!",
                "role": "manager"
            },
            {
                "email": "employee@company.com",
                "username": "employee_user", 
                "full_name": "John Employee",
                "password": "employee123!",
                "role": "employee"
            }
        ]
        
        success_count = 0
        for user_data in test_users:
            try:
                response = self.session.post(f"{self.base_url}/auth/register", json=user_data)
                if response.status_code == 200:
                    user_info = response.json()
                    self.users[user_data["role"]] = {
                        "user_data": user_data,
                        "user_info": user_info
                    }
                    self.log(f"✅ Successfully registered {user_data['role']}: {user_data['username']}")
                    success_count += 1
                else:
                    self.log(f"❌ Failed to register {user_data['role']}: {response.status_code} - {response.text}", "ERROR")
            except Exception as e:
                self.log(f"❌ Exception during {user_data['role']} registration: {str(e)}", "ERROR")
        
        return success_count == len(test_users)
    
    def test_user_login(self):
        """Test user login and token generation"""
        self.log("=== Testing User Login & JWT Token Generation ===")
        
        success_count = 0
        for role, user_info in self.users.items():
            try:
                login_data = {
                    "username": user_info["user_data"]["username"],
                    "password": user_info["user_data"]["password"]
                }
                
                response = self.session.post(f"{self.base_url}/auth/login", json=login_data)
                if response.status_code == 200:
                    token_data = response.json()
                    self.tokens[role] = token_data["access_token"]
                    self.log(f"✅ Successfully logged in {role}: {login_data['username']}")
                    success_count += 1
                else:
                    self.log(f"❌ Failed to login {role}: {response.status_code} - {response.text}", "ERROR")
            except Exception as e:
                self.log(f"❌ Exception during {role} login: {str(e)}", "ERROR")
        
        return success_count == len(self.users)
    
    def test_token_validation(self):
        """Test JWT token validation and user profile retrieval"""
        self.log("=== Testing JWT Token Validation ===")
        
        success_count = 0
        for role, token in self.tokens.items():
            try:
                headers = {"Authorization": f"Bearer {token}"}
                response = self.session.get(f"{self.base_url}/auth/me", headers=headers)
                
                if response.status_code == 200:
                    user_profile = response.json()
                    expected_role = self.users[role]["user_data"]["role"]
                    if user_profile["role"] == expected_role:
                        self.log(f"✅ Token validation successful for {role}")
                        success_count += 1
                    else:
                        self.log(f"❌ Role mismatch for {role}: expected {expected_role}, got {user_profile['role']}", "ERROR")
                else:
                    self.log(f"❌ Token validation failed for {role}: {response.status_code}", "ERROR")
            except Exception as e:
                self.log(f"❌ Exception during token validation for {role}: {str(e)}", "ERROR")
        
        return success_count == len(self.tokens)
    
    def test_project_management(self):
        """Test project CRUD operations with role-based access"""
        self.log("=== Testing Project Management CRUD ===")
        
        # Test project creation by manager
        project_data = {
            "name": "Mobile App Development",
            "description": "Developing a new mobile application for customer engagement",
            "start_date": datetime.now().isoformat(),
            "end_date": (datetime.now() + timedelta(days=90)).isoformat(),
            "assigned_employees": [self.users["employee"]["user_info"]["id"]]
        }
        
        # Manager creates project
        try:
            headers = {"Authorization": f"Bearer {self.tokens['manager']}"}
            response = self.session.post(f"{self.base_url}/projects", json=project_data, headers=headers)
            
            if response.status_code == 200:
                project = response.json()
                self.projects["main_project"] = project
                self.log("✅ Manager successfully created project")
            else:
                self.log(f"❌ Manager failed to create project: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Exception during project creation: {str(e)}", "ERROR")
            return False
        
        # Test employee access to assigned project
        try:
            headers = {"Authorization": f"Bearer {self.tokens['employee']}"}
            response = self.session.get(f"{self.base_url}/projects", headers=headers)
            
            if response.status_code == 200:
                projects = response.json()
                if len(projects) > 0 and projects[0]["id"] == self.projects["main_project"]["id"]:
                    self.log("✅ Employee can access assigned project")
                else:
                    self.log("❌ Employee cannot access assigned project", "ERROR")
                    return False
            else:
                self.log(f"❌ Employee failed to get projects: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Exception during employee project access: {str(e)}", "ERROR")
            return False
        
        # Test admin access to all projects
        try:
            headers = {"Authorization": f"Bearer {self.tokens['admin']}"}
            response = self.session.get(f"{self.base_url}/projects", headers=headers)
            
            if response.status_code == 200:
                projects = response.json()
                if len(projects) > 0:
                    self.log("✅ Admin can access all projects")
                else:
                    self.log("❌ Admin cannot access projects", "ERROR")
                    return False
            else:
                self.log(f"❌ Admin failed to get projects: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Exception during admin project access: {str(e)}", "ERROR")
            return False
        
        return True
    
    def test_timesheet_management(self):
        """Test complete timesheet CRUD operations"""
        self.log("=== Testing Timesheet Management System ===")
        
        # Employee creates timesheet
        timesheet_data = {
            "project_id": self.projects["main_project"]["id"],
            "date": datetime.now().isoformat(),
            "hours": 8.0,
            "description": "Worked on user authentication module and API integration"
        }
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens['employee']}"}
            response = self.session.post(f"{self.base_url}/timesheets", json=timesheet_data, headers=headers)
            
            if response.status_code == 200:
                timesheet = response.json()
                self.timesheets["main_timesheet"] = timesheet
                self.log("✅ Employee successfully created timesheet")
                
                # Verify timesheet is in draft status
                if timesheet["status"] == "draft":
                    self.log("✅ Timesheet created in draft status")
                else:
                    self.log(f"❌ Timesheet status incorrect: expected 'draft', got '{timesheet['status']}'", "ERROR")
                    return False
            else:
                self.log(f"❌ Employee failed to create timesheet: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Exception during timesheet creation: {str(e)}", "ERROR")
            return False
        
        # Employee submits timesheet
        try:
            update_data = {"status": "submitted"}
            timesheet_id = self.timesheets["main_timesheet"]["id"]
            headers = {"Authorization": f"Bearer {self.tokens['employee']}"}
            response = self.session.put(f"{self.base_url}/timesheets/{timesheet_id}", json=update_data, headers=headers)
            
            if response.status_code == 200:
                updated_timesheet = response.json()
                if updated_timesheet["status"] == "submitted":
                    self.log("✅ Employee successfully submitted timesheet")
                    self.timesheets["main_timesheet"] = updated_timesheet
                else:
                    self.log(f"❌ Timesheet status not updated: {updated_timesheet['status']}", "ERROR")
                    return False
            else:
                self.log(f"❌ Employee failed to submit timesheet: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Exception during timesheet submission: {str(e)}", "ERROR")
            return False
        
        # Test employee can only see their own timesheets
        try:
            headers = {"Authorization": f"Bearer {self.tokens['employee']}"}
            response = self.session.get(f"{self.base_url}/timesheets", headers=headers)
            
            if response.status_code == 200:
                timesheets = response.json()
                employee_id = self.users["employee"]["user_info"]["id"]
                all_employee_timesheets = all(ts["employee_id"] == employee_id for ts in timesheets)
                
                if all_employee_timesheets:
                    self.log("✅ Employee can only see their own timesheets")
                else:
                    self.log("❌ Employee can see other employees' timesheets", "ERROR")
                    return False
            else:
                self.log(f"❌ Employee failed to get timesheets: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Exception during employee timesheet access: {str(e)}", "ERROR")
            return False
        
        return True
    
    def test_approval_workflow(self):
        """Test timesheet approval/rejection workflow"""
        self.log("=== Testing Approval Workflow ===")
        
        timesheet_id = self.timesheets["main_timesheet"]["id"]
        
        # Manager approves timesheet
        try:
            approval_data = {
                "status": "approved",
                "rejection_reason": None
            }
            headers = {"Authorization": f"Bearer {self.tokens['manager']}"}
            response = self.session.post(f"{self.base_url}/timesheets/{timesheet_id}/approve", json=approval_data, headers=headers)
            
            if response.status_code == 200:
                approved_timesheet = response.json()
                if approved_timesheet["status"] == "approved" and approved_timesheet["approved_by"]:
                    self.log("✅ Manager successfully approved timesheet")
                    self.timesheets["main_timesheet"] = approved_timesheet
                else:
                    self.log(f"❌ Timesheet approval failed: status={approved_timesheet['status']}", "ERROR")
                    return False
            else:
                self.log(f"❌ Manager failed to approve timesheet: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Exception during timesheet approval: {str(e)}", "ERROR")
            return False
        
        # Test employee cannot approve timesheets
        try:
            rejection_data = {
                "status": "rejected",
                "rejection_reason": "Insufficient details"
            }
            headers = {"Authorization": f"Bearer {self.tokens['employee']}"}
            response = self.session.post(f"{self.base_url}/timesheets/{timesheet_id}/approve", json=rejection_data, headers=headers)
            
            if response.status_code == 403:
                self.log("✅ Employee correctly denied access to approval endpoint")
            else:
                self.log(f"❌ Employee should not have access to approval: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Exception during employee approval test: {str(e)}", "ERROR")
            return False
        
        return True
    
    def test_dashboard_analytics(self):
        """Test dashboard summary endpoint with role-based statistics"""
        self.log("=== Testing Dashboard Analytics API ===")
        
        # Test employee dashboard
        try:
            headers = {"Authorization": f"Bearer {self.tokens['employee']}"}
            response = self.session.get(f"{self.base_url}/dashboard/summary", headers=headers)
            
            if response.status_code == 200:
                dashboard_data = response.json()
                required_fields = ["total_hours", "approved_hours", "pending_hours", "total_projects", "total_timesheets"]
                
                if all(field in dashboard_data for field in required_fields):
                    self.log("✅ Employee dashboard contains all required fields")
                    self.log(f"   Employee Stats: {dashboard_data}")
                else:
                    missing_fields = [field for field in required_fields if field not in dashboard_data]
                    self.log(f"❌ Employee dashboard missing fields: {missing_fields}", "ERROR")
                    return False
            else:
                self.log(f"❌ Employee dashboard failed: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Exception during employee dashboard test: {str(e)}", "ERROR")
            return False
        
        # Test manager dashboard
        try:
            headers = {"Authorization": f"Bearer {self.tokens['manager']}"}
            response = self.session.get(f"{self.base_url}/dashboard/summary", headers=headers)
            
            if response.status_code == 200:
                dashboard_data = response.json()
                required_fields = ["total_hours", "approved_hours", "pending_approvals", "total_projects", "total_employees", "total_timesheets"]
                
                if all(field in dashboard_data for field in required_fields):
                    self.log("✅ Manager dashboard contains all required fields")
                    self.log(f"   Manager Stats: {dashboard_data}")
                else:
                    missing_fields = [field for field in required_fields if field not in dashboard_data]
                    self.log(f"❌ Manager dashboard missing fields: {missing_fields}", "ERROR")
                    return False
            else:
                self.log(f"❌ Manager dashboard failed: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Exception during manager dashboard test: {str(e)}", "ERROR")
            return False
        
        return True
    
    def test_role_based_access_control(self):
        """Test comprehensive role-based access restrictions"""
        self.log("=== Testing Role-Based Access Control ===")
        
        # Test employee cannot create projects
        try:
            project_data = {
                "name": "Unauthorized Project",
                "description": "This should fail",
                "start_date": datetime.now().isoformat()
            }
            headers = {"Authorization": f"Bearer {self.tokens['employee']}"}
            response = self.session.post(f"{self.base_url}/projects", json=project_data, headers=headers)
            
            if response.status_code == 403:
                self.log("✅ Employee correctly denied project creation access")
            else:
                self.log(f"❌ Employee should not be able to create projects: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Exception during employee project creation test: {str(e)}", "ERROR")
            return False
        
        # Test employee cannot access other users' timesheets
        try:
            manager_id = self.users["manager"]["user_info"]["id"]
            headers = {"Authorization": f"Bearer {self.tokens['employee']}"}
            response = self.session.get(f"{self.base_url}/timesheets?employee_id={manager_id}", headers=headers)
            
            if response.status_code == 200:
                timesheets = response.json()
                employee_id = self.users["employee"]["user_info"]["id"]
                # Should only return employee's own timesheets, not manager's
                all_employee_timesheets = all(ts["employee_id"] == employee_id for ts in timesheets)
                
                if all_employee_timesheets:
                    self.log("✅ Employee access properly restricted to own timesheets")
                else:
                    self.log("❌ Employee can access other users' timesheets", "ERROR")
                    return False
            else:
                self.log(f"❌ Employee timesheet access test failed: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ Exception during employee timesheet access test: {str(e)}", "ERROR")
            return False
        
        return True
    
    def run_all_tests(self):
        """Run all backend tests in sequence"""
        self.log("🚀 Starting Comprehensive Backend Testing Suite")
        self.log(f"Backend URL: {self.base_url}")
        
        test_results = {}
        
        # Test sequence
        tests = [
            ("User Registration", self.test_user_registration),
            ("User Login & JWT", self.test_user_login),
            ("Token Validation", self.test_token_validation),
            ("Project Management", self.test_project_management),
            ("Timesheet Management", self.test_timesheet_management),
            ("Approval Workflow", self.test_approval_workflow),
            ("Dashboard Analytics", self.test_dashboard_analytics),
            ("Role-Based Access Control", self.test_role_based_access_control)
        ]
        
        for test_name, test_func in tests:
            self.log(f"\n{'='*60}")
            try:
                result = test_func()
                test_results[test_name] = result
                status = "✅ PASSED" if result else "❌ FAILED"
                self.log(f"{test_name}: {status}")
            except Exception as e:
                test_results[test_name] = False
                self.log(f"{test_name}: ❌ FAILED - {str(e)}", "ERROR")
        
        # Summary
        self.log(f"\n{'='*60}")
        self.log("🏁 TEST SUMMARY")
        self.log(f"{'='*60}")
        
        passed = sum(1 for result in test_results.values() if result)
        total = len(test_results)
        
        for test_name, result in test_results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            self.log(f"{test_name:<30} {status}")
        
        self.log(f"\nOverall Result: {passed}/{total} tests passed")
        
        if passed == total:
            self.log("🎉 ALL TESTS PASSED - Backend system is working correctly!")
            return True
        else:
            self.log(f"⚠️  {total - passed} tests failed - Backend system has issues")
            return False

if __name__ == "__main__":
    tester = TimesheetBackendTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)