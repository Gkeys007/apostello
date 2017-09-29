module Pages.InboundTable exposing (view)

import Data exposing (SmsInbound)
import FilteringTable as FT
import Helpers exposing (formatDate)
import Html exposing (Html, a, b, i, td, text, th, thead, tr)
import Html.Attributes as A
import Html.Events as E
import Messages exposing (Msg(StoreMsg))
import Pages exposing (Page(ContactForm, KeywordForm), initSendAdhoc)
import Pages.Forms.Contact.Model exposing (initialContactFormModel)
import Pages.Forms.Keyword.Model exposing (initialKeywordFormModel)
import RemoteList as RL
import Rocket exposing ((=>))
import Route exposing (spaLink)
import Store.Messages exposing (StoreMsg(ReprocessSms))


-- Main view


view : FT.Model -> RL.RemoteList SmsInbound -> Html Msg
view tableModel sms =
    let
        head =
            thead []
                [ tr []
                    [ th [] [ text "From" ]
                    , th [] [ text "Keyword" ]
                    , th [] [ text "Message" ]
                    , th [] [ text "Time" ]
                    , th [] []
                    ]
                ]
    in
    FT.defaultTable head tableModel smsRow sms


smsRow : SmsInbound -> ( String, Html Msg )
smsRow sms =
    ( toString sms.pk
    , tr [ A.style [ "backgroundColor" => sms.matched_colour ] ]
        [ recipientCell sms
        , keywordCell sms
        , td [] [ text sms.content ]
        , td [] [ text (formatDate sms.time_received) ]
        , reprocessCell sms
        ]
    )


recipientCell : SmsInbound -> Html Msg
recipientCell sms =
    let
        replyPage =
            initSendAdhoc Nothing <| Maybe.map List.singleton sms.sender_pk

        contactPage =
            ContactForm initialContactFormModel <| sms.sender_pk
    in
    td []
        [ spaLink a [] [ i [ A.class "fa fa-reply", A.style [ "color" => "var(--state-primary)" ] ] [] ] replyPage
        , spaLink a [ A.style [ "color" => "#212121" ] ] [ text sms.sender_name ] contactPage
        ]


keywordCell : SmsInbound -> Html Msg
keywordCell sms =
    case sms.matched_keyword of
        "#" ->
            td [] [ b [] [ text sms.matched_keyword ] ]

        "No Match" ->
            td [] [ b [] [ text sms.matched_keyword ] ]

        _ ->
            td []
                [ b []
                    [ spaLink a
                        [ A.style [ ( "color", "#212121" ) ] ]
                        [ text sms.matched_keyword ]
                        (KeywordForm initialKeywordFormModel <| Just sms.matched_keyword)
                    ]
                ]


reprocessCell : SmsInbound -> Html Msg
reprocessCell sms =
    td []
        [ a
            [ A.class "button button-info"
            , A.id "reingestButton"
            , E.onClick (StoreMsg (ReprocessSms sms.pk))
            ]
            [ text "Reprocess" ]
        ]
