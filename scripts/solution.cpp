/**
 * Definition for singly-linked list.
 * struct ListNode {
 *     int val;
 *     ListNode *next;
 *     ListNode() : val(0), next(nullptr) {}
 *     ListNode(int x) : val(x), next(nullptr) {}
 *     ListNode(int x, ListNode *next) : val(x), next(next) {}
 * };
 */
/**
 * Definition for singly-linked list.
 * struct ListNode {
 *     int val;
 *     ListNode *next;
 *     ListNode() : val(0), next(nullptr) {}
 *     ListNode(int x) : val(x), next(nullptr) {}
 *     ListNode(int x, ListNode *next) : val(x), next(next) {}
 * };
 */
class Solution {
public:
    ListNode* mergeKLists(vector<ListNode*>& lists){
        int num = lists.size();
        vector<ListNode*> headlist;
    
        ListNode* ans = new ListNode();
        ListNode* anshead =ans;
        for(int i = 0; i <num;i++){
            ListNode *head = new ListNode(); 
            cout<<"lists[i]" <<lists[i] <<endl;
            head->next = lists[i];
            headlist.push_back(head);
        }
        while(headlist.size() != 0){
            int tmp = 0;
            int ins = 0;
            int minvalue = INT_MAX;
            
            for(int ins = headlist.size()-1;ins >=0;ins--){
                ListNode * head = headlist[ins];
                cout<< "head->next" << head->next << endl;
                if(head->next == nullptr){
                    headlist.erase(headlist.begin()+ins);
                    cout<< "erase" << ins << endl;
                    cout<< "headlist" << headlist.size() <<endl; 
                    continue;
                }
                if(head->next->val < minvalue){
                    minvalue = head->next->val;
                    tmp = ins;
                    cout<<"tt" << tmp <<endl;
                }

            }
            cout<<"tmp" << tmp << endl;
            
            if(headlist[tmp]->next!= nullptr){
                ans->next = headlist[tmp]->next;
                cout<<"ans" << ans->next->val << endl;
                headlist[tmp]->next = headlist[tmp]->next->next;
            }
            ans = ans->next;
        }
        return anshead->next;
    }
};
// lists[i]0
// lists[i]0x6020000016b0
// lists[i]0
// lists[i]0x602000001730


// head->next0x602000001730
// head->next0
// erase2
// headlist3
// head->next0x6020000016b0
// head->next0
// erase0
// headlist2
// tmp1
// ans6
// head->next0x602000001750
// head->next0x6020000016b0
// tmp0
// ans-1
// head->next0x602000001750
// head->next0x6020000016d0
// tmp0
// ans5
// head->next0x602000001750
// head->next0x6020000016f0
// tmp1
// ans10
// head->next0
// erase1
// headlist1
// head->next0x6020000016f0
// tmp0
// ans11
// head->next0
// erase0
// headlist0
// tmp0